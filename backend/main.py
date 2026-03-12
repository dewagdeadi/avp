import os
import uuid
import json
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# MUST be imported first to set FFmpeg on PATH
import core.config  # noqa

from core.downloader import download_video
from core.audio_analysis import extract_best_segment
from core.video_processing import track_and_crop_faces
from core.captioning import generate_subtitles, burn_subtitles
from core.thumbnail import generate_thumbnail

# Ensure the downloads directory exists BEFORE app startup
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__) or ".", "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

app = FastAPI(title="AI Video Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount downloads for static file serving
app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

# In-memory job store
jobs: dict = {}

class VideoRequest(BaseModel):
    youtube_url: str

# ── History helpers ────────────────────────────────────────────────────────────

def _scan_history() -> list[dict]:
    """Rebuild history from job dirs that have a completed final_short.mp4."""
    history = []
    if not os.path.isdir(DOWNLOADS_DIR):
        return history
    for job_id in os.listdir(DOWNLOADS_DIR):
        job_dir = os.path.join(DOWNLOADS_DIR, job_id)
        final   = os.path.join(job_dir, "final_short.mp4")
        meta_f  = os.path.join(job_dir, "meta.json")
        if not os.path.isfile(final):
            continue
        meta = {}
        if os.path.isfile(meta_f):
            try:
                with open(meta_f, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
        # Find thumbnail
        thumb_url = None
        for fname in os.listdir(job_dir):
            if fname.endswith("_thumb.jpg"):
                thumb_url = f"/downloads/{job_id}/{fname}"
                break
        history.append({
            "job_id":      job_id,
            "url":         f"/downloads/{job_id}/final_short.mp4",
            "thumbnail":   thumb_url,
            "youtube_url": meta.get("youtube_url", ""),
            "detail":      meta.get("detail", ""),
            "created_at":  meta.get("created_at", ""),
        })
    history.sort(key=lambda x: x["created_at"], reverse=True)
    return history

def _save_meta(job_id: str, data: dict):
    meta_f = os.path.join(DOWNLOADS_DIR, job_id, "meta.json")
    try:
        with open(meta_f, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def _update(job_id: str, status: str, progress: int, detail: str, **extra):
    jobs[job_id] = {"status": status, "progress": progress, "detail": detail, "url": None, **extra}

# ── Pipeline ──────────────────────────────────────────────────────────────────

async def process_video_pipeline(youtube_url: str, job_id: str):
    job_dir = os.path.join(DOWNLOADS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    # Save meta immediately so history can reference the source URL
    _save_meta(job_id, {
        "youtube_url": youtube_url,
        "created_at":  datetime.utcnow().isoformat(),
    })

    try:
        _update(job_id, "downloading", 8, "Connecting to YouTube and fetching video stream...")

        dl_path = download_video(youtube_url, output_path=job_dir)
        if not dl_path:
            raise Exception("Failed to download video")

        file_mb = os.path.getsize(dl_path) / (1024 * 1024)
        _update(job_id, "analyzing_audio", 22, f"Downloaded {file_mb:.0f} MB — scanning audio to find the best hook...")

        start_t, end_t = extract_best_segment(dl_path, target_length_sec=45)
        clip_len = end_t - start_t

        _update(job_id, "trimming", 32,
                f"Clipping {clip_len:.0f}s segment ({_fmt_time(start_t)} → {_fmt_time(end_t)}) with frame-accurate re-encode...")

        import subprocess
        from core.config import VIDEO_ENCODER_ARGS
        trimmed_path = os.path.join(job_dir, "trimmed.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(start_t),
            "-i", dl_path,
            "-t", str(clip_len),
            *VIDEO_ENCODER_ARGS,
            "-c:a", "aac",
            "-b:a", "192k",
            trimmed_path
        ], check=True)

        _update(job_id, "tracking_faces", 48,
                "Detecting faces frame-by-frame — spring-damper camera panning to 9:16...")

        cropped_path = os.path.join(job_dir, "cropped.mp4")
        track_success = track_and_crop_faces(trimmed_path, cropped_path)
        if not track_success:
            raise Exception("Face tracking/cropping failed")

        _update(job_id, "generating_captions", 65,
                "Transcribing speech with Whisper AI (small model, Indonesian) — word-level timing...")

        srt_path = generate_subtitles(cropped_path, model_size="small", language="id")

        try:
            n_captions = srt_path and sum(1 for l in open(srt_path, encoding="utf-8") if l.startswith("Dialogue:"))
        except Exception:
            n_captions = 0

        _update(job_id, "rendering_final", 80,
                f"Burning {n_captions} caption groups into video with libass renderer...")

        final_path = os.path.join(job_dir, "final_short.mp4")
        burn_subtitles(cropped_path, srt_path, final_path)

        final_mb = os.path.getsize(final_path) / (1024 * 1024)
        _update(job_id, "generating_thumbnail", 92,
                f"Final video is {final_mb:.1f} MB — picking best frame for thumbnail...")

        thumb_path = generate_thumbnail(final_path)

        public_url = f"/downloads/{job_id}/final_short.mp4"
        thumb_url  = f"/downloads/{job_id}/{os.path.basename(thumb_path)}" if thumb_path else None
        detail     = f"Done! {clip_len:.0f}s short • {final_mb:.1f} MB • {n_captions} caption groups"

        jobs[job_id] = {
            "status": "completed", "progress": 100,
            "detail": detail, "url": public_url, "thumbnail": thumb_url
        }

        # Persist to meta.json so history survives restarts
        _save_meta(job_id, {
            "youtube_url": youtube_url,
            "created_at":  datetime.utcnow().isoformat(),
            "detail":      detail,
        })

    except Exception as e:
        print(f"Pipeline error for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        jobs[job_id] = {"status": "failed", "progress": 0, "detail": str(e), "error": str(e), "url": None}

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/process")
async def process_video_endpoint(req: VideoRequest, background_tasks: BackgroundTasks):
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    jobs[job_id] = {"status": "queued", "progress": 0, "url": None}
    background_tasks.add_task(process_video_pipeline, req.youtube_url, job_id)
    return {"message": "Processing started", "job_id": job_id}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        return {"status": "not_found"}
    return jobs[job_id]

@app.get("/api/history")
async def get_history():
    return _scan_history()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
