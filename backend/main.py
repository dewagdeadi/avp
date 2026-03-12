import os
import uuid
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

async def process_video_pipeline(youtube_url: str, job_id: str):
    """
    Background task: Downloads YT video, finds the best segment,
    crops to 9:16 with face tracking, adds captions, and generates thumbnail.
    """
    job_dir = os.path.join(DOWNLOADS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    try:
        jobs[job_id] = {"status": "downloading", "progress": 10, "url": None}
        
        # 1. Download
        dl_path = download_video(youtube_url, output_path=job_dir)
        if not dl_path:
            raise Exception("Failed to download video")
            
        jobs[job_id] = {"status": "analyzing_audio", "progress": 30, "url": None}
        
        # 2. Find Best Segment
        start_t, end_t = extract_best_segment(dl_path, target_length_sec=45)
        
        # Trim with re-encode for frame-accurate A/V sync
        import subprocess
        from core.config import VIDEO_ENCODER_ARGS
        trimmed_path = os.path.join(job_dir, "trimmed.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(start_t),
            "-i", dl_path,
            "-t", str(end_t - start_t),
            *VIDEO_ENCODER_ARGS,
            "-c:a", "aac",
            "-b:a", "192k",
            trimmed_path
        ], check=True)
        
        jobs[job_id] = {"status": "tracking_faces", "progress": 50, "url": None}
        
        # 3. Face Track and Crop
        cropped_path = os.path.join(job_dir, "cropped.mp4")
        track_success = track_and_crop_faces(trimmed_path, cropped_path)
        if not track_success:
            raise Exception("Face tracking/cropping failed")
            
        jobs[job_id] = {"status": "generating_captions", "progress": 70, "url": None}
        
        # 4. Auto-caption (Whisper) — force Indonesian language for accuracy
        srt_path = generate_subtitles(cropped_path, model_size="small", language="id")
        
        jobs[job_id] = {"status": "rendering_final", "progress": 85, "url": None}
        
        # 5. Burn Subtitles
        final_path = os.path.join(job_dir, "final_short.mp4")
        burn_subtitles(cropped_path, srt_path, final_path)
        
        jobs[job_id] = {"status": "generating_thumbnail", "progress": 92, "url": None}
        
        # 6. Generate thumbnail
        thumb_path = generate_thumbnail(final_path)
        
        # Return paths
        public_url = f"/downloads/{job_id}/final_short.mp4"
        thumb_url = f"/downloads/{job_id}/{os.path.basename(thumb_path)}" if thumb_path else None
        jobs[job_id] = {"status": "completed", "progress": 100, "url": public_url, "thumbnail": thumb_url}
        
    except Exception as e:
        print(f"Pipeline error for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        jobs[job_id] = {"status": "failed", "progress": 0, "error": str(e), "url": None}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
