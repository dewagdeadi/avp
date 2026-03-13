import os
import subprocess
from faster_whisper import WhisperModel
from core.config import VIDEO_ENCODER_ARGS, USE_NVENC

# Singleton: load model once, reuse across jobs
_whisper_model: WhisperModel | None = None
_whisper_model_size: str = ""

def _get_whisper_model(model_size: str) -> WhisperModel:
    global _whisper_model, _whisper_model_size
    if _whisper_model is None or _whisper_model_size != model_size:
        device = "cuda" if USE_NVENC else "cpu"
        compute_type = "int8_float32" if device == "cuda" else "int8"
        print(f"[captioning] Loading Whisper '{model_size}' on {device} ({compute_type})...")
        _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
        _whisper_model_size = model_size
    return _whisper_model

def generate_subtitles(video_path: str, model_size="small", language="id") -> tuple[str, str]:
    """
    Uses faster-whisper to generate an ASS subtitle file with WORD-LEVEL timing
    for tight sync between voice and on-screen text.
    language='id' forces Bahasa Indonesia recognition.
    Returns (ass_path, full_transcript_text).
    """
    print(f"Generating captions for {video_path} using Whisper ({model_size}, lang={language})...")
    model = _get_whisper_model(model_size)
    
    # Force Indonesian language for better accuracy
    segments_gen, info = model.transcribe(
        video_path, 
        language=language,
        word_timestamps=True,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=300,
        ),
    )
    
    # Collect all segments first (generator)
    segments = list(segments_gen)
    
    print(f"Detected language '{info.language}' with probability {info.language_probability}")
    print(f"Found {len(segments)} segments")
    
    # Generate ASS subtitle file
    ass_path = video_path.rsplit('.', 1)[0] + '.ass'
    
    with open(ass_path, 'w', encoding='utf-8') as f:
        # ASS file header
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write("PlayResX: 1080\n")
        f.write("PlayResY: 1920\n")
        f.write("WrapStyle: 0\n")
        f.write("\n")
        
        # Style: Bold white text, thick black outline, centered bottom
        # This is the "Indo viral shorts" look
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Arial Black,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,2,40,40,80,1\n")
        f.write("\n")
        
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        # === WORD-LEVEL TIMING for tight sync ===
        # Group words into short phrases (3-5 words) for readability
        # Each phrase appears exactly when the first word is spoken
        # and disappears when the last word finishes
        
        for segment in segments:
            if not segment.words:
                # Fallback: use segment-level timing if no word timestamps
                start_ass = _seconds_to_ass_time(segment.start)
                end_ass = _seconds_to_ass_time(segment.end)
                text = segment.text.strip().upper()
                f.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}\n")
                continue
            
            # Group words into short phrases of ~4 words each
            words = list(segment.words)
            chunk_size = 4
            
            for i in range(0, len(words), chunk_size):
                chunk = words[i:i + chunk_size]
                
                # Timing: start when first word is spoken, end when last word ends
                chunk_start = chunk[0].start
                chunk_end = chunk[-1].end
                
                # Build the phrase text
                phrase = " ".join(w.word.strip() for w in chunk).upper()
                
                if not phrase.strip():
                    continue
                
                start_ass = _seconds_to_ass_time(chunk_start)
                end_ass = _seconds_to_ass_time(chunk_end)
                
                f.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{phrase}\n")

    # Collect full transcript for hook generation
    full_transcript = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

    print(f"ASS subtitle file saved: {ass_path}")
    return ass_path, full_transcript

def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format: H:MM:SS.CC"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
    
def burn_subtitles(video_path: str, sub_path: str, output_path: str):
    """
    Uses FFmpeg to burn ASS subtitles into the video.
    """
    print(f"Burning subtitles onto {video_path}...")
    
    # Escape Windows paths for FFmpeg filter
    safe_sub_path = sub_path.replace('\\', '/')
    if ':' in safe_sub_path:
        safe_sub_path = safe_sub_path.replace(':', '\\:')
    
    vf_arg = f"ass='{safe_sub_path}'"
    
    command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf_arg,
        *VIDEO_ENCODER_ARGS,
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ]
    
    print("Running command:", " ".join(command))
    subprocess.run(command, check=True)
    print(f"Captioned video saved to {output_path}")
    return output_path

if __name__ == "__main__":
    pass
