"""
Central configuration for the yt-dlp API.
All tuneable values live here; override via environment variables.
"""

import os

# ── Server ─────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/ytdlp_cache")

# ── Cache ──────────────────────────────────────────────────────────────────
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL", 3600))       # 1 hour
CACHE_CLEANUP_INTERVAL = int(os.getenv("CACHE_CLEANUP", 900))  # 15 min
MAX_CACHE_SIZE_MB = int(os.getenv("MAX_CACHE_MB", 5120))    # 5 GB

# ── Cookies ────────────────────────────────────────────────────────────────
# Path to a cookies file (Netscape/txt or JSON). Leave blank to disable.
COOKIES_FILE = os.getenv("COOKIES_FILE", "")
# Auto-detect cookies.txt or cookies.json in project root if env not set
if not COOKIES_FILE:
    for _name in ("cookies.txt", "cookies.json"):
        _path = os.path.join(BASE_DIR, _name)
        if os.path.isfile(_path):
            COOKIES_FILE = _path
            break

# ── yt-dlp ─────────────────────────────────────────────────────────────────
YTDLP_CONCURRENT_FRAGMENTS = int(os.getenv("YTDLP_CONCURRENT_FRAGMENTS", 4))
YTDLP_SOCKET_TIMEOUT = int(os.getenv("YTDLP_SOCKET_TIMEOUT", 20))
YTDLP_RETRIES = int(os.getenv("YTDLP_RETRIES", 5))
YTDLP_USER_AGENT = os.getenv(
    "YTDLP_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

# ── Branding ───────────────────────────────────────────────────────────────
BRAND_SUFFIX = os.getenv("BRAND_SUFFIX", "by_me.gifted.co.ke")

# ── Audio quality presets (yt-dlp preferredquality string) ─────────────────
AUDIO_QUALITY_MAP = {
    "best":   "320",
    "high":   "256",
    "medium": "192",
    "low":    "128",
    "worst":  "64",
    # allow raw kbps values like "320", "192", etc.
}

# ── Video quality presets (max height) ─────────────────────────────────────
VIDEO_QUALITY_MAP = {
    "best":   None,     # no height cap → yt-dlp picks best
    "4k":     2160,
    "2160p":  2160,
    "1440p":  1440,
    "2k":     1440,
    "1080p":  1080,
    "1080p60":1080,
    "720p":   720,
    "720p60": 720,
    "480p":   480,
    "360p":   360,
    "240p":   240,
    "144p":   144,
    "worst":  144,
}

# ── Search defaults ─────────────────────────────────────────────────────────
DEFAULT_SEARCH_LIMIT = int(os.getenv("DEFAULT_SEARCH_LIMIT", 10))
MAX_SEARCH_LIMIT = int(os.getenv("MAX_SEARCH_LIMIT", 50))
