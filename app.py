"""
yt-dlp YouTube Download API
============================
A fast, production-ready Flask API for searching, streaming, and downloading
YouTube audio and video via yt-dlp.

Endpoints
---------
GET  /                               - API documentation
GET  /api/health                     - Health / status check
GET  /api/search?q=...               - YouTube search or URL resolve
GET  /api/info?url=...               - Video metadata
GET  /api/formats?url=...            - Available formats for a video
GET  /api/download/audio?url=...     - Download audio as MP3
GET  /api/download/video?url=...     - Download video as MP4
GET  /api/cache/stats                - Cache statistics
DELETE /api/cache/clear              - Manually purge cache
"""

import logging
import os
import time

from flask import Flask, jsonify, request, send_file, abort
from flask_cors import CORS

import config
from lib import cache
from lib.cookies import resolve_cookie_file
from lib.downloader import download_audio, download_video
from lib.searcher import search, get_info, get_formats
from lib.utils import clean_info, format_size, is_youtube_url

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# Start background cache cleaner
cache.start()


# ── Helpers ────────────────────────────────────────────────────────────────

def _cookie_file() -> str | None:
    """Resolve cookies from the request or server config."""
    raw = (
        request.args.get("cookies")
        or request.headers.get("X-Cookies")
        or None
    )
    return resolve_cookie_file(raw)


def _ok(data, **kwargs) -> tuple:
    return jsonify({"status": "ok", **kwargs, "data": data}), 200


def _err(msg: str, code: int = 400) -> tuple:
    return jsonify({"status": "error", "message": str(msg)}), code


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    """API root — returns documentation overview."""
    return jsonify({
        "name": "yt-dlp YouTube API",
        "version": "1.0.0",
        "brand": config.BRAND_SUFFIX,
        "base_url": request.host_url.rstrip("/"),
        "endpoints": {
            "search":         "GET /api/search?q=<query|url>&limit=10",
            "info":           "GET /api/info?url=<youtube_url>",
            "formats":        "GET /api/formats?url=<youtube_url>",
            "download_audio": "GET /api/download/audio?url=<youtube_url>&quality=best",
            "download_video": "GET /api/download/video?url=<youtube_url>&quality=720p",
            "cache_stats":    "GET /api/cache/stats",
            "cache_clear":    "DELETE /api/cache/clear",
            "health":         "GET /api/health",
        },
        "audio_qualities": list(config.AUDIO_QUALITY_MAP.keys()),
        "video_qualities": list(config.VIDEO_QUALITY_MAP.keys()),
        "cookies": (
            "Pass via ?cookies=<data> query param or X-Cookies header. "
            "Accepts Netscape cookies.txt, JSON dict/list, or Cookie header string."
        ),
    })


@app.get("/api/health")
def health():
    """Liveness / readiness probe."""
    cs = cache.stats()
    return jsonify({
        "status": "ok",
        "cache": cs,
        "uptime_hint": "use /api/cache/stats for details",
    })


@app.get("/api/search")
def api_search():
    """
    Search YouTube or resolve a URL.

    Query params
    ------------
    q       : (required) Search keyword or YouTube URL.
    limit   : Max results (default 10, max 50).
    cookies : Optional cookie data (Netscape / JSON / header string).
    """
    q = request.args.get("q", "").strip()
    if not q:
        return _err("Missing required param: q", 400)

    try:
        limit = int(request.args.get("limit", config.DEFAULT_SEARCH_LIMIT))
    except ValueError:
        return _err("limit must be an integer", 400)

    try:
        t0 = time.perf_counter()
        results = search(q, limit=limit, cookie_file=_cookie_file())
        elapsed = round(time.perf_counter() - t0, 3)
        return _ok(results, count=len(results), elapsed_seconds=elapsed)
    except Exception as exc:
        logger.exception("Search error")
        return _err(str(exc), 500)


@app.get("/api/info")
def api_info():
    """
    Return full metadata for a YouTube video.

    Query params
    ------------
    url     : (required) YouTube video URL.
    cookies : Optional cookie data.
    """
    url = request.args.get("url", "").strip()
    if not url:
        return _err("Missing required param: url", 400)

    try:
        t0 = time.perf_counter()
        raw = get_info(url, cookie_file=_cookie_file())
        elapsed = round(time.perf_counter() - t0, 3)
        return _ok(clean_info(raw), elapsed_seconds=elapsed)
    except Exception as exc:
        logger.exception("Info error")
        return _err(str(exc), 500)


@app.get("/api/formats")
def api_formats():
    """
    Return available download formats for a video.

    Query params
    ------------
    url     : (required) YouTube video URL.
    cookies : Optional cookie data.
    """
    url = request.args.get("url", "").strip()
    if not url:
        return _err("Missing required param: url", 400)

    try:
        fmts = get_formats(url, cookie_file=_cookie_file())
        return _ok(fmts, count=len(fmts))
    except Exception as exc:
        logger.exception("Formats error")
        return _err(str(exc), 500)


@app.get("/api/download/audio")
def api_download_audio():
    """
    Download and return a YouTube video as an MP3 file.

    Query params
    ------------
    url     : (required) YouTube video URL or search keyword.
    quality : Audio quality — best (320kbps), high (256), medium (192),
              low (128), worst (64). Also accepts raw kbps e.g. '192'.
              Default: best.
    cookies : Optional cookie data.

    Response
    --------
    audio/mpeg file download with a branded filename.
    """
    url = request.args.get("url", "").strip()
    if not url:
        return _err("Missing required param: url", 400)

    # Allow keyword search → pick first result
    if not is_youtube_url(url):
        try:
            results = search(url, limit=1, cookie_file=_cookie_file())
            if not results:
                return _err(f"No YouTube results found for: {url}", 404)
            url = results[0]["url"]
            logger.info("Resolved search '%s' → %s", request.args.get("url"), url)
        except Exception as exc:
            return _err(f"Search failed: {exc}", 500)

    quality = request.args.get("quality", "best").strip().lower()

    try:
        t0 = time.perf_counter()
        path = download_audio(url, quality=quality, cookie_file=_cookie_file())
        elapsed = round(time.perf_counter() - t0, 3)
        size = os.path.getsize(path)
        filename = os.path.basename(path)
        logger.info(
            "Serving audio %s  size=%s  elapsed=%.2fs",
            filename, format_size(size), elapsed,
        )
        return send_file(
            path,
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        logger.exception("Audio download error")
        return _err(str(exc), 500)


@app.get("/api/download/video")
def api_download_video():
    """
    Download and return a YouTube video as an MP4 file.

    Query params
    ------------
    url     : (required) YouTube video URL or search keyword.
    quality : Video quality — best, 4k, 1080p, 720p, 480p, 360p, 240p, 144p,
              worst. Also accepts raw height e.g. '720'. Default: 720p.
    cookies : Optional cookie data.

    Response
    --------
    video/mp4 file download with a branded filename.
    """
    url = request.args.get("url", "").strip()
    if not url:
        return _err("Missing required param: url", 400)

    # Allow keyword search → pick first result
    if not is_youtube_url(url):
        try:
            results = search(url, limit=1, cookie_file=_cookie_file())
            if not results:
                return _err(f"No YouTube results found for: {url}", 404)
            url = results[0]["url"]
            logger.info("Resolved search '%s' → %s", request.args.get("url"), url)
        except Exception as exc:
            return _err(f"Search failed: {exc}", 500)

    quality = request.args.get("quality", "720p").strip().lower()

    try:
        t0 = time.perf_counter()
        path = download_video(url, quality=quality, cookie_file=_cookie_file())
        elapsed = round(time.perf_counter() - t0, 3)
        size = os.path.getsize(path)
        filename = os.path.basename(path)
        logger.info(
            "Serving video %s  size=%s  elapsed=%.2fs",
            filename, format_size(size), elapsed,
        )
        return send_file(
            path,
            mimetype="video/mp4",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        logger.exception("Video download error")
        return _err(str(exc), 500)


@app.get("/api/cache/stats")
def api_cache_stats():
    """Return current cache statistics."""
    return _ok(cache.stats())


@app.delete("/api/cache/clear")
def api_cache_clear():
    """Manually purge all expired cache entries."""
    removed = cache.cleanup()
    return _ok({"removed": removed}, message=f"Removed {removed} expired entries")


# ── Error handlers ─────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_e):
    return _err("Endpoint not found", 404)


@app.errorhandler(405)
def method_not_allowed(_e):
    return _err("Method not allowed", 405)


@app.errorhandler(500)
def server_error(e):
    logger.exception("Unhandled server error")
    return _err("Internal server error", 500)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(
        "Starting yt-dlp API on %s:%d  debug=%s",
        config.HOST, config.PORT, config.DEBUG,
    )
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
