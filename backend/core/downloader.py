import yt_dlp
import os
import glob

MIN_FILE_MB = 150
MAX_FILE_MB = 800
MIN_HEIGHT = 720  # Minimum resolution to avoid pixelated video


def _cleanup_part_files(directory: str):
    """Remove any leftover .part files from failed/aborted downloads."""
    for f in glob.glob(os.path.join(directory, "*.part")):
        try:
            os.remove(f)
            print(f"Cleaned up: {f}")
        except Exception:
            pass


def estimate_size(youtube_url: str) -> dict | None:
    """
    Probe a YouTube video WITHOUT downloading.
    Returns dict with: title, duration, height, est_mb, format_id
    or None if unsuitable.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
    except Exception as e:
        print(f"[downloader] Probe failed: {e}")
        return None

    if not info:
        return None

    title = info.get("title", "")
    duration = info.get("duration") or 0
    formats = info.get("formats") or []

    # Find the best video+audio combo within our limits
    # Sort video formats by quality (height desc) then filesize
    video_fmts = [
        f for f in formats
        if f.get("vcodec", "none") != "none"
        and (f.get("height") or 0) >= MIN_HEIGHT
    ]
    audio_fmts = [
        f for f in formats
        if f.get("acodec", "none") != "none"
        and f.get("vcodec", "none") == "none"
    ]

    if not video_fmts:
        print(f"[downloader] No video stream >= {MIN_HEIGHT}p found")
        return None

    # Sort by height descending (best quality first)
    video_fmts.sort(key=lambda f: (f.get("height") or 0), reverse=True)

    # Best audio (highest bitrate)
    audio_fmts.sort(key=lambda f: (f.get("abr") or f.get("tbr") or 0), reverse=True)
    audio_size = 0
    if audio_fmts:
        a = audio_fmts[0]
        audio_size = a.get("filesize") or a.get("filesize_approx") or 0

    # Pick the best video that fits within MAX_FILE_MB
    best = None
    for vf in video_fmts:
        vsize = vf.get("filesize") or vf.get("filesize_approx") or 0

        # If no filesize info, estimate from bitrate
        if vsize == 0:
            tbr = vf.get("tbr") or vf.get("vbr") or 0
            if tbr > 0 and duration > 0:
                vsize = int(tbr * 1000 / 8 * duration)  # bits to bytes

        total_mb = (vsize + audio_size) / (1024 * 1024)

        # Still no estimate — rough guess from resolution + duration
        if total_mb < 1 and duration > 0:
            h = vf.get("height") or 720
            # ~2 Mbps for 720p, ~4 for 1080p, ~8 for 1440p
            bps = 2_000_000 if h <= 720 else 4_000_000 if h <= 1080 else 8_000_000
            total_mb = (bps / 8 * duration + audio_size) / (1024 * 1024)

        if total_mb > MAX_FILE_MB:
            continue  # Too big, try lower quality

        best = {
            "title": title,
            "duration": duration,
            "height": vf.get("height") or 0,
            "est_mb": round(total_mb, 1),
            "format_id": vf.get("format_id", ""),
            "audio_format_id": audio_fmts[0].get("format_id", "") if audio_fmts else "",
        }
        break  # Take the highest quality that fits

    if not best:
        # All formats too big — take the smallest video stream
        vf = video_fmts[-1]
        vsize = vf.get("filesize") or vf.get("filesize_approx") or 0
        total_mb = (vsize + audio_size) / (1024 * 1024)
        print(f"[downloader] All formats exceed {MAX_FILE_MB} MB (smallest ~{total_mb:.0f} MB)")
        return None

    if best["est_mb"] < MIN_FILE_MB:
        print(f"[downloader] Estimated {best['est_mb']} MB < {MIN_FILE_MB} MB minimum")
        return None

    print(f"[downloader] Pre-check OK: {best['title'][:50]}... "
          f"— {best['height']}p, ~{best['est_mb']} MB")
    return best


def download_video(youtube_url: str, output_path: str = "downloads", format_id: str = None, audio_format_id: str = None) -> str:
    """
    Downloads a YouTube video in the highest quality available.
    If format_id is provided, downloads that specific format.
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    _cleanup_part_files(output_path)

    final_path = os.path.join(output_path, "source.mp4")

    # Use specific format if provided (from estimate_size), else best available
    if format_id and audio_format_id:
        fmt = f"{format_id}+{audio_format_id}"
    elif format_id:
        fmt = f"{format_id}+bestaudio"
    else:
        fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

    ydl_opts = {
        'format': fmt,
        'outtmpl': os.path.join(output_path, "source.%(ext)s"),
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading {youtube_url} (format: {fmt})...")
            info = ydl.extract_info(youtube_url, download=True)
            raw_filename = ydl.prepare_filename(info)

            if not raw_filename.endswith('.mp4'):
                raw_filename = raw_filename.rsplit('.', 1)[0] + '.mp4'

            if raw_filename != final_path and os.path.exists(raw_filename):
                os.rename(raw_filename, final_path)

            if os.path.exists(final_path):
                print(f"Download complete: {final_path}")
                return final_path

            print(f"Warning: Expected {final_path}, got {raw_filename}")
            return raw_filename
    except Exception as e:
        print(f"Error downloading video: {e}")
        _cleanup_part_files(output_path)
        return ""


if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    info = estimate_size(url)
    if info:
        print(f"Title:  {info['title']}")
        print(f"Size:   ~{info['est_mb']} MB")
        print(f"Height: {info['height']}p")
    else:
        print("Video not suitable")
