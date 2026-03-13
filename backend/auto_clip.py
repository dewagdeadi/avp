"""
Auto-clip trending Indonesian podcasts.
Finds a trending podcast → downloads → clips best segment → crops 9:16 →
adds captions → generates thumbnail with hook text.

Run standalone: python auto_clip.py
Scheduled: runs via Windows Task Scheduler every 24h
"""
import os
import sys
import uuid
import json
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

# Must import config first to set FFmpeg on PATH
import core.config  # noqa

from core.trending import find_trending_podcast, mark_as_processed
from core.downloader import download_video, estimate_size
from core.audio_analysis import extract_best_segment
from core.video_processing import track_and_crop_faces
from core.captioning import generate_subtitles, burn_subtitles
from core.thumbnail import generate_thumbnail
from core.hook_generator import generate_hook_text
from core.watermark_detect import detect_watermark
from core.db import add_job
from core.config import VIDEO_ENCODER_ARGS

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
LOG_FILE = os.path.join(DOWNLOADS_DIR, "auto_clip.log")


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def auto_clip():
    """Full pipeline: find trending → process → save."""
    _log("=== Auto-clip started ===")

    # Step 1: Find trending podcast
    _log("Step 1/7: Searching for trending podcast...")
    video = find_trending_podcast()
    if not video:
        _log("ERROR: No trending podcast found. Will retry next cycle.")
        return None

    _log(f"Found: {video['title']} ({video['channel']}) — {video['view_count']:,} views")
    _log(f"URL: {video['url']}")

    # Step 1.5: Estimate file size BEFORE downloading
    _log("Checking video size & quality before download...")
    probe = estimate_size(video["url"])
    if not probe:
        _log("SKIPPED: Video doesn't meet size/quality requirements (pre-check)")
        mark_as_processed(video["id"], video.get("title", ""), video.get("url", ""), video.get("channel", ""), video.get("view_count", 0))
        return None
    _log(f"Pre-check: {probe['height']}p, ~{probe['est_mb']} MB — OK")

    job_id = f"auto_{uuid.uuid4().hex[:8]}"
    job_dir = os.path.join(DOWNLOADS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    try:
        # Step 2: Download (using the pre-selected format)
        _log(f"Step 2/7: Downloading {probe['height']}p video (~{probe['est_mb']} MB)...")
        dl_path = download_video(
            video["url"], output_path=job_dir,
            format_id=probe.get("format_id"),
            audio_format_id=probe.get("audio_format_id"),
        )
        if not dl_path:
            raise Exception("Download failed")
        file_mb = os.path.getsize(dl_path) / (1024 * 1024)
        _log(f"Downloaded: {file_mb:.0f} MB (estimated {probe['est_mb']} MB)")

        # Check for watermark — skip if detected
        _log("Checking for watermarks...")
        if detect_watermark(dl_path):
            _log("SKIPPED: Watermark detected in video")
            mark_as_processed(video["id"], video.get("title", ""), video.get("url", ""), video.get("channel", ""), video.get("view_count", 0))
            import shutil
            shutil.rmtree(job_dir, ignore_errors=True)
            return None
        _log("No watermark — proceeding")

        # Step 3: Analyze audio & find best segment
        _log("Step 3/7: Analyzing audio for best hook segment...")
        start_t, end_t = extract_best_segment(dl_path, target_length_sec=45)
        clip_len = end_t - start_t
        _log(f"Best segment: {_fmt_time(start_t)} → {_fmt_time(end_t)} ({clip_len:.0f}s)")

        # Step 4: Trim
        _log("Step 4/7: Trimming clip...")
        import subprocess
        trimmed_path = os.path.join(job_dir, "trimmed.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(start_t),
            "-i", dl_path,
            "-t", str(clip_len),
            *VIDEO_ENCODER_ARGS,
            "-c:a", "aac", "-b:a", "192k",
            trimmed_path
        ], check=True)

        # Step 5: Face track & crop to 9:16
        _log("Step 5/7: Face tracking & cropping to 9:16...")
        cropped_path = os.path.join(job_dir, "cropped.mp4")
        if not track_and_crop_faces(trimmed_path, cropped_path):
            raise Exception("Face tracking failed")

        # Step 6: Captions
        _log("Step 6/7: Generating captions with Whisper...")
        srt_path, transcript = generate_subtitles(cropped_path, model_size="small", language="id")

        final_path = os.path.join(job_dir, "final_short.mp4")
        burn_subtitles(cropped_path, srt_path, final_path)
        final_mb = os.path.getsize(final_path) / (1024 * 1024)

        # Step 7: Thumbnail with hook text
        _log("Step 7/7: Generating thumbnail with hook text...")
        hook_text = generate_hook_text(transcript, language="id")
        thumb_path = generate_thumbnail(final_path, caption_text=hook_text)

        # Count captions
        try:
            n_captions = sum(1 for l in open(srt_path, encoding="utf-8") if l.startswith("Dialogue:"))
        except Exception:
            n_captions = 0

        detail = f"{video['title'][:60]} | {clip_len:.0f}s • {final_mb:.1f} MB • {n_captions} captions"

        # Save meta
        meta = {
            "youtube_url": video["url"],
            "title": video["title"],
            "channel": video["channel"],
            "view_count": video["view_count"],
            "hook_text": hook_text,
            "detail": detail,
            "created_at": datetime.utcnow().isoformat(),
            "auto_generated": True,
        }
        with open(os.path.join(job_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

        # Cleanup intermediate files to save disk space
        for tmp in [dl_path, trimmed_path, cropped_path, srt_path]:
            try:
                if tmp and os.path.isfile(tmp):
                    os.remove(tmp)
            except Exception:
                pass
        _log("Cleaned up intermediate files")

        # Mark as processed so we don't pick it again
        mark_as_processed(video["id"], video.get("title", ""), video.get("url", ""), video.get("channel", ""), video.get("view_count", 0), job_id)

        # Save job to database
        add_job(
            job_id=job_id, video_id=video["id"],
            youtube_url=video["url"], title=video.get("title", ""),
            channel=video.get("channel", ""), hook_text=hook_text,
            detail=detail, file_mb=final_mb, auto=True,
        )

        _log(f"=== DONE! Job {job_id} ===")
        _log(f"  Video: {final_path}")
        _log(f"  Thumb: {thumb_path}")
        _log(f"  Hook:  {hook_text}")
        _log(f"  Size:  {final_mb:.1f} MB")

        return {
            "job_id": job_id,
            "video_path": final_path,
            "thumbnail_path": thumb_path,
            "hook_text": hook_text,
            "source": video,
        }

    except Exception as e:
        _log(f"ERROR: Pipeline failed — {e}")
        import traceback
        traceback.print_exc()
        return None


LOCK_FILE = os.path.join(DOWNLOADS_DIR, "auto_clip.lock")

if __name__ == "__main__":
    # Prevent multiple instances running at the same time
    if os.path.isfile(LOCK_FILE):
        print("Another auto-clip is already running. Exiting.")
        sys.exit(0)

    try:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))

        result = auto_clip()
        if result:
            print(f"\nSuccess! Clip saved as {result['job_id']}")
        else:
            print("\nFailed — check auto_clip.log for details")
    finally:
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass
