import yt_dlp
import os

def download_video(youtube_url: str, output_path: str = "downloads") -> str:
    """
    Downloads a YouTube video in the highest quality available.
    Now that FFmpeg is installed, we can download separate video+audio streams
    and let yt-dlp merge them for maximum resolution (1080p+).
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    final_path = os.path.join(output_path, "source.mp4")
    
    ydl_opts = {
        # Download best video + best audio, merge into mp4
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
        'outtmpl': os.path.join(output_path, "source.%(ext)s"),
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading {youtube_url} (highest quality)...")
            info = ydl.extract_info(youtube_url, download=True)
            raw_filename = ydl.prepare_filename(info)
            
            # yt-dlp may output with different extension before merge
            # The final merged file should be .mp4
            if not raw_filename.endswith('.mp4'):
                raw_filename = raw_filename.rsplit('.', 1)[0] + '.mp4'
            
            # Rename to our standard name if needed
            if raw_filename != final_path and os.path.exists(raw_filename):
                os.rename(raw_filename, final_path)
            
            if os.path.exists(final_path):
                print(f"Download complete: {final_path}")
                return final_path
            
            # Fallback
            print(f"Warning: Expected {final_path}, got {raw_filename}")
            return raw_filename
    except Exception as e:
        print(f"Error downloading video: {e}")
        return ""

if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    res = download_video(url)
    print(f"Saved to: {res}")
