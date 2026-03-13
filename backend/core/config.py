"""
Shared config for the backend.
"""
import os
import sys
import subprocess

# FFmpeg path - winget installs it here on Windows
FFMPEG_DIR = r"C:\Users\PC\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin"
FFMPEG_PATH = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
FFPROBE_PATH = os.path.join(FFMPEG_DIR, "ffprobe.exe")

def ensure_ffmpeg_on_path():
    """Add FFmpeg to the current process PATH if not already there."""
    if FFMPEG_DIR not in os.environ.get("PATH", ""):
        os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
        print(f"[config] Added FFmpeg to PATH: {FFMPEG_DIR}")

def _check_nvenc() -> bool:
    """Return True if h264_nvenc actually works (driver + GPU compatible)."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner",
                "-f", "lavfi", "-i", "color=c=black:size=128x128:duration=0.1",
                "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20",
                "-f", "null", "-"
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.returncode == 0
    except Exception:
        return False

# Add NVIDIA cuBLAS DLLs to PATH (needed by CTranslate2 / faster-whisper)
_CUBLAS_BIN = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cublas", "bin")
if os.path.isdir(_CUBLAS_BIN) and _CUBLAS_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _CUBLAS_BIN + os.pathsep + os.environ.get("PATH", "")
    print(f"[config] Added cuBLAS to PATH: {_CUBLAS_BIN}")

# Auto-add on import
ensure_ffmpeg_on_path()

# Detect GPU encoder once at startup
USE_NVENC: bool = _check_nvenc()
if USE_NVENC:
    print("[config] NVIDIA NVENC detected — GPU encoding enabled.")
    VIDEO_ENCODER_ARGS = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-pix_fmt", "yuv420p"]
else:
    print("[config] NVENC not available — falling back to libx264.")
    VIDEO_ENCODER_ARGS = ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p"]
