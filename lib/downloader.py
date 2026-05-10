"""
yt-dlp download wrappers for audio and video.

Both functions check the file cache before downloading.  On a cache miss,
the file is downloaded to CACHE_DIR with a branded filename, registered in
the cache, and its path is returned.
"""

import os
import logging
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

import config
from lib import cache
from lib.utils import sanitize_filename, extract_video_id

logger = logging.getLogger(__name__)


# ── Shared yt-dlp base options ─────────────────────────────────────────────


def _base_opts(cookie_file: str | None) -> dict:
    opts = {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
        "retries": config.YTDLP_RETRIES,
        "socket_timeout": config.YTDLP_SOCKET_TIMEOUT,
        "concurrent_fragment_downloads": config.YTDLP_CONCURRENT_FRAGMENTS,
        "http_headers": {"User-Agent": config.YTDLP_USER_AGENT},
        "progress_hooks": [],
        # Avoid interactive prompts
        "noprogress": True,
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


# ── Audio download ─────────────────────────────────────────────────────────


def download_audio(
    url: str,
    quality: str = "best",
    cookie_file: str | None = None,
) -> str:
    """
    Download the best audio from *url*, convert to MP3, and return the path.

    Parameters
    ----------
    url         : YouTube video / shorts / playlist URL (first entry only).
    quality     : One of config.AUDIO_QUALITY_MAP keys or a raw kbps string.
    cookie_file : Path to Netscape-format cookies file, or None.

    Returns
    -------
    Absolute path to the downloaded MP3 file.
    """
    # Resolve quality → kbps string
    kbps = config.AUDIO_QUALITY_MAP.get(quality.lower(), quality)
    # Guard: must be a numeric string
    if not kbps.rstrip("k").isdigit():
        kbps = "320"

    video_id = extract_video_id(url) or _slugify(url)
    cache_key = f"{video_id}_audio_{kbps}kbps"

    cached = cache.get(cache_key)
    if cached:
        logger.info("Returning cached audio: %s", cached)
        return cached

    # Ensure cache dir exists
    Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)

    # Temporary output template (yt-dlp fills in the real title)
    outtmpl = os.path.join(config.CACHE_DIR, f"{cache_key}_%(title)s.%(ext)s")

    opts = _base_opts(cookie_file)
    opts.update({
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": kbps,
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
        ],
    })

    logger.info("Downloading audio  url=%s quality=%skbps", url, kbps)

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except (DownloadError, ExtractorError) as exc:
        raise RuntimeError(f"Audio download failed: {exc}") from exc

    title = (info or {}).get("title", cache_key)

    # Locate the downloaded MP3 (yt-dlp may append extra chars)
    mp3_path = _find_output(config.CACHE_DIR, cache_key, "mp3")
    if not mp3_path:
        raise RuntimeError("Downloaded audio file not found in cache dir")

    # Rename to branded filename
    final_name = sanitize_filename(title, "mp3")
    final_path = os.path.join(config.CACHE_DIR, final_name)
    if mp3_path != final_path:
        os.rename(mp3_path, final_path)

    cache.put(cache_key, final_path)
    logger.info("Audio ready: %s  size=%d bytes", final_path, os.path.getsize(final_path))
    return final_path


# ── Video download ─────────────────────────────────────────────────────────


def download_video(
    url: str,
    quality: str = "best",
    cookie_file: str | None = None,
) -> str:
    """
    Download video (with audio merged) from *url* and return its path.

    Parameters
    ----------
    url         : YouTube video / shorts URL.
    quality     : One of config.VIDEO_QUALITY_MAP keys, e.g. '720p', 'best'.
    cookie_file : Path to Netscape-format cookies file, or None.

    Returns
    -------
    Absolute path to the downloaded MP4 file.
    """
    max_height = config.VIDEO_QUALITY_MAP.get(quality.lower())
    # Allow raw numeric strings like "720"
    if max_height is None and quality.rstrip("p").isdigit():
        max_height = int(quality.rstrip("p"))

    video_id = extract_video_id(url) or _slugify(url)
    q_tag = f"{max_height}p" if max_height else "best"
    cache_key = f"{video_id}_video_{q_tag}"

    cached = cache.get(cache_key)
    if cached:
        logger.info("Returning cached video: %s", cached)
        return cached

    Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)
    outtmpl = os.path.join(config.CACHE_DIR, f"{cache_key}_%(title)s.%(ext)s")

    # Build format selector
    if max_height:
        fmt = (
            f"bestvideo[height<={max_height}][ext=mp4]"
            f"+bestaudio[ext=m4a]"
            f"/bestvideo[height<={max_height}]+bestaudio"
            f"/best[height<={max_height}]"
            f"/best"
        )
    else:
        fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

    opts = _base_opts(cookie_file)
    opts.update({
        "format": fmt,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "postprocessors": [
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            }
        ],
    })

    logger.info("Downloading video  url=%s quality=%s", url, q_tag)

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except (DownloadError, ExtractorError) as exc:
        raise RuntimeError(f"Video download failed: {exc}") from exc

    title = (info or {}).get("title", cache_key)

    mp4_path = _find_output(config.CACHE_DIR, cache_key, "mp4")
    if not mp4_path:
        raise RuntimeError("Downloaded video file not found in cache dir")

    final_name = sanitize_filename(title, "mp4")
    final_path = os.path.join(config.CACHE_DIR, final_name)
    if mp4_path != final_path:
        # Avoid overwriting if same title and already exists
        if not os.path.exists(final_path):
            os.rename(mp4_path, final_path)
        else:
            final_path = mp4_path  # keep original name

    cache.put(cache_key, final_path)
    logger.info("Video ready: %s  size=%d bytes", final_path, os.path.getsize(final_path))
    return final_path


# ── Internal helpers ───────────────────────────────────────────────────────


def _find_output(directory: str, prefix: str, ext: str) -> str | None:
    """Find the first file in *directory* that starts with *prefix* and ends with *.ext*."""
    try:
        for name in os.listdir(directory):
            if name.startswith(prefix) and name.endswith(f".{ext}"):
                return os.path.join(directory, name)
    except FileNotFoundError:
        pass
    return None


def _slugify(url: str) -> str:
    """Fallback ID from URL when video ID cannot be extracted."""
    import re
    return re.sub(r"[^a-zA-Z0-9]", "_", url)[-40:]
