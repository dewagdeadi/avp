"""
Find trending Indonesian podcast videos on YouTube using yt-dlp search.
Uses SQLite for tracking processed videos.
"""
import yt_dlp
import os
import random
from datetime import datetime

from core.db import get_processed_ids, add_processed, migrate_from_json

# One-time migration from old JSON format
_HISTORY_JSON = os.path.join(os.path.dirname(__file__), "..", "downloads", "auto_history.json")
if os.path.isfile(_HISTORY_JSON):
    migrate_from_json(_HISTORY_JSON)

# Also scan existing meta.json files and migrate those
_DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "downloads")
if os.path.isdir(_DOWNLOADS_DIR):
    _existing_ids = get_processed_ids()
    for _job_name in os.listdir(_DOWNLOADS_DIR):
        _meta_path = os.path.join(_DOWNLOADS_DIR, _job_name, "meta.json")
        if os.path.isfile(_meta_path):
            try:
                import json
                with open(_meta_path, "r", encoding="utf-8") as _f:
                    _meta = json.load(_f)
                _yt_url = _meta.get("youtube_url", "")
                if "v=" in _yt_url:
                    _vid_id = _yt_url.split("v=")[1].split("&")[0]
                    if _vid_id not in _existing_ids:
                        add_processed(
                            video_id=_vid_id,
                            title=_meta.get("title", ""),
                            url=_yt_url,
                            channel=_meta.get("channel", ""),
                        )
                        _existing_ids.add(_vid_id)
            except Exception:
                pass

# Search queries — focused on funny/comedy Indonesian podcasts
SEARCH_QUERIES = [
    "podcast lucu indonesia terbaru",
    "podcast komedi indonesia viral",
    "podcast ngakak indonesia",
    "podcast lucu deddy corbuzier",
    "podcast kocak indonesia trending",
    "close the door podcast lucu terbaru",
    "podcast indonesia ngakak abis",
    "podcast lawak indonesia terbaru",
    "podcast komedi viral indonesia 2026",
    "podkesmas lucu terbaru",
    "podcast receh indonesia",
    "podcast stand up komedi indonesia",
]


def find_trending_podcast(max_results: int = 15) -> dict | None:
    """
    Search YouTube for a trending Indonesian podcast video.
    Returns dict with: id, url, title, channel, duration, view_count
    or None if nothing found.
    """
    processed_ids = get_processed_ids()

    query = random.choice(SEARCH_QUERIES)
    print(f"[trending] Searching: '{query}'")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
        "ignoreerrors": True,
    }

    candidates = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_url = f"ytsearch{max_results}:{query}"
            result = ydl.extract_info(search_url, download=False)

            if not result or "entries" not in result:
                print("[trending] No search results")
                return None

            for entry in result["entries"]:
                if entry is None:
                    continue

                vid_id = entry.get("id", "")
                duration = entry.get("duration") or 0
                view_count = entry.get("view_count") or 0
                title = entry.get("title", "")
                channel = entry.get("channel", "") or entry.get("uploader", "")

                if vid_id in processed_ids:
                    continue

                if duration < 300 or duration > 7200:
                    continue

                title_lower = title.lower()
                if any(skip in title_lower for skip in ["#shorts", "music video", "mv official", "trailer"]):
                    continue

                candidates.append({
                    "id": vid_id,
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "title": title,
                    "channel": channel,
                    "duration": duration,
                    "view_count": view_count,
                })

    except Exception as e:
        print(f"[trending] Search error: {e}")
        return None

    if not candidates:
        print("[trending] No new candidates found")
        return None

    candidates.sort(key=lambda x: x["view_count"], reverse=True)

    pick = candidates[0]
    print(f"[trending] Picked: {pick['title']} ({pick['channel']}) — {pick['view_count']:,} views, {pick['duration']//60}min")

    return pick


def mark_as_processed(video_id: str, title: str = "", url: str = "",
                      channel: str = "", view_count: int = 0, job_id: str = ""):
    """Mark a video as processed so we don't clip it again."""
    add_processed(
        video_id=video_id, title=title, url=url,
        channel=channel, view_count=view_count, job_id=job_id,
    )
    count = len(get_processed_ids())
    print(f"[trending] Marked {video_id} as processed ({count} total)")


if __name__ == "__main__":
    video = find_trending_podcast()
    if video:
        print(f"\nFound: {video['title']}")
        print(f"URL:   {video['url']}")
        print(f"Views: {video['view_count']:,}")
    else:
        print("No trending podcast found")
