import os
import subprocess
import re

def analyze_audio_peaks(video_path: str, min_silence_len_sec: float = 1.0, silence_thresh: str = "-40dB"):
    """
    Analyzes the audio track of a video using FFmpeg to find non-silent segments.
    Returns a list of tuples: (start_time_sec, end_time_sec)
    """
    print(f"Analyzing audio for {video_path}...")
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
            "-af", f"silencedetect=noise={silence_thresh}:d={min_silence_len_sec}",
            "-f", "null", "-"
        ]
        
        # FFmpeg outputs log to stderr
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        output = result.stderr
        
        silences = []
        for line in output.split('\n'):
            if "silence_start:" in line:
                match = re.search(r"silence_start:\s+([\d\.]+)", line)
                if match:
                    silences.append({"type": "start", "time": float(match.group(1))})
            elif "silence_end:" in line:
                match = re.search(r"silence_end:\s+([\d\.]+)", line)
                if match:
                    silences.append({"type": "end", "time": float(match.group(1))})
                    
        # Find video duration to bound the last segment
        duration_match = re.search(r"Duration:\s+([\d]+):([\d]+):([\d\.]+)", output)
        video_duration = 999.0
        if duration_match:
            hours, text_mins, text_secs = duration_match.groups()
            video_duration = int(hours) * 3600 + int(text_mins) * 60 + float(text_secs)
            
        # Convert silences to speech segments
        segments = []
        current_time = 0.0
        
        for event in silences:
            if event["type"] == "start":
                if event["time"] > current_time:
                    segments.append((current_time, event["time"]))
            elif event["type"] == "end":
                current_time = event["time"]
                
        # Add the final trailing segment if speech continues to the end
        if current_time < video_duration:
            segments.append((current_time, video_duration))
            
        return segments

    except Exception as e:
        print(f"Error analyzing audio with ffmpeg: {e}")
        return []

def extract_best_segment(video_path: str, target_length_sec: int = 45):
    """
    Finds the most active contiguous segment of roughly target_length_sec.
    """
    segments = analyze_audio_peaks(video_path)
    if not segments:
        return (0, target_length_sec)
        
    # Skip introductory silence by starting at the first speech segment
    best_start = segments[0][0]
    
    # Simple logic: take the first block of talking
    best_end = best_start + target_length_sec
    
    return (best_start, best_end)

if __name__ == "__main__":
    pass
