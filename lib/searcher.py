"""
YouTube search using yt-dlp's native search backend.

Supports
--------
- Keyword queries  → ``ytsearch{limit}:{query}``
- Direct URLs      → any https://youtube.com/* or https://youtu.be/* link
  (including Shorts, playlists, live streams)
"""

import logging
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

from lib.utils import format_duration, is_youtube_url
import config

logger = logging.getLogger(__name__)


# ── yt-dlp option builder ──────────────────────────────────────────────────


def _base_opts(cookie_file: str | None = None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",     # don't recurse into every video
        "noplaylist": False,               # allow playlist extraction
        "ignoreerrors": True,
        "socket_timeout": config.YTDLP_SOCKET_TIMEOUT,
        "http_headers": {"User-Agent": config.YTDLP_USER_AGENT},
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


# ── Public API ─────────────────────────────────────────────────────────────


def search(
    query: str,
    limit: int = config.DEFAULT_SEARCH_LIMIT,
    cookie_file: str | None = None,
) -> list[dict[str, Any]]:
    """
    Search YouTube or resolve a direct URL.

    Parameters
    ----------
    query       : Search keyword OR a YouTube URL.
    limit       : Max results (ignored when *query* is a URL).
    cookie_file : Path to a Netscape-format cookies file, or None.

    Returns
    -------
    List of result dicts, each containing:
      id, title, url, uploader, duration, duration_string,
      view_count, thumbnail, live_status, webpage_url
    """
    limit = min(max(1, limit), config.MAX_SEARCH_LIMIT)

    if is_youtube_url(query):
        source = query
        logger.info("Resolving URL: %s", query)
    else:
        source = f"ytsearch{limit}:{query}"
        logger.info("Searching YouTube: %r  limit=%d", query, limit)

    opts = _base_opts(cookie_file)

    try:
        with YoutubeDL(opts) as ydl:
            raw = ydl.extract_info(source, download=False)
    except (DownloadError, ExtractorError) as exc:
        logger.error("Search failed: %s", exc)
        raise RuntimeError(str(exc)) from exc

    if raw is None:
        return []

    entries = raw.get("entries") or [raw]
    results = []
    for entry in entries:
        if not entry:
            continue
        results.append(_format_entry(entry))

    logger.info("Search returned %d results", len(results))
    return results


def get_info(url: str, cookie_file: str | None = None) -> dict[str, Any]:
    """
    Fetch detailed metadata for a single video URL.

    Returns the full yt-dlp info dict (formats stripped for brevity in the
    API response — callers can use get_formats() for the format list).
    """
    logger.info("Fetching info for: %s", url)
    opts = _base_opts(cookie_file)
    opts["extract_flat"] = False  # need full info for one video

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except (DownloadError, ExtractorError) as exc:
        logger.error("get_info failed: %s", exc)
        raise RuntimeError(str(exc)) from exc

    if info is None:
        raise RuntimeError("No info returned by yt-dlp")

    return info


def get_formats(url: str, cookie_file: str | None = None) -> list[dict]:
    """
    Return the list of available formats for *url*, cleaned up for JSON.
    """
    info = get_info(url, cookie_file)
    raw_fmts = info.get("formats") or []
    results = []
    for f in raw_fmts:
        results.append({
            "format_id":    f.get("format_id"),
            "ext":          f.get("ext"),
            "resolution":   f.get("resolution") or f.get("format_note"),
            "fps":          f.get("fps"),
            "vcodec":       f.get("vcodec"),
            "acodec":       f.get("acodec"),
            "has_video":    (f.get("vcodec") or "none") != "none",
            "has_audio":    (f.get("acodec") or "none") != "none",
            "quality_label":f.get("format_note"),
            "height":       f.get("height"),
            "width":        f.get("width"),
            "tbr":          f.get("tbr"),      # total bitrate kbps
            "abr":          f.get("abr"),      # audio bitrate kbps
            "vbr":          f.get("vbr"),      # video bitrate kbps
            "filesize":     f.get("filesize") or f.get("filesize_approx"),
            "protocol":     f.get("protocol"),
        })
    return results


# ── Internal helpers ───────────────────────────────────────────────────────


def _format_entry(entry: dict) -> dict:
    duration = entry.get("duration")
    return {
        "id":              entry.get("id"),
        "title":           entry.get("title"),
        "url":             entry.get("webpage_url") or entry.get("url"),
        "uploader":        entry.get("uploader") or entry.get("channel"),
        "uploader_id":     entry.get("uploader_id") or entry.get("channel_id"),
        "duration":        duration,
        "duration_string": format_duration(duration),
        "view_count":      entry.get("view_count"),
        "like_count":      entry.get("like_count"),
        "thumbnail":       entry.get("thumbnail"),
        "live_status":     entry.get("live_status"),
        "is_live":         entry.get("is_live") or entry.get("live_status") == "is_live",
        "upload_date":     entry.get("upload_date"),
        "description":     (entry.get("description") or "")[:300] or None,
    }
