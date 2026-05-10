"""
Utility helpers: filename sanitisation, human-readable formatting.
"""

import re
import os
from werkzeug.utils import secure_filename
import config


def sanitize_filename(title: str, ext: str) -> str:
    """
    Build a branded, filesystem-safe filename.

    Examples
    --------
    >>> sanitize_filename("Rick Astley - Never Gonna Give You Up", "mp3")
    'Rick_Astley_-_Never_Gonna_Give_You_Up_by_me.gifted.co.ke.mp3'
    """
    safe = secure_filename(title)
    # secure_filename may strip everything — fall back to a hash
    if not safe:
        safe = "video"
    safe = safe.replace(" ", "_")
    return f"{safe}_{config.BRAND_SUFFIX}.{ext}"


def format_size(num_bytes: int | None) -> str:
    """Return a human-readable file size string."""
    if num_bytes is None:
        return "unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def format_duration(seconds: int | float | None) -> str:
    """Return HH:MM:SS or MM:SS string from seconds."""
    if seconds is None:
        return "unknown"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def is_youtube_url(text: str) -> bool:
    """Return True if *text* looks like a YouTube URL."""
    pattern = re.compile(
        r"(https?://)?(www\.)?"
        r"(youtube\.com/(watch|shorts|embed|playlist|live)|youtu\.be/)",
        re.IGNORECASE,
    )
    return bool(pattern.search(text))


def extract_video_id(url: str) -> str | None:
    """Extract the YouTube video ID from a URL, or None if not found."""
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/(?:watch\?.*v=|embed/|shorts/|live/)([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def clean_info(info: dict) -> dict:
    """
    Strip binary / very large fields from a yt-dlp info dict before
    returning it as JSON so the response stays lean.
    """
    skip = {
        "formats", "requested_formats", "thumbnails", "automatic_captions",
        "subtitles", "heatmap", "fragments", "http_headers",
        "_format_sort_fields", "format_sort_fields",
    }
    return {k: v for k, v in info.items() if k not in skip and not k.startswith("_")}
