# yt-dlp YouTube Download API

A **blazing-fast**, production-ready REST API for searching, streaming, and downloading YouTube audio and video — powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [Flask](https://flask.palletsprojects.com/).

**Live API:** https://ytdlp.gifted.co.ke

---

## Features

- **YouTube Search** — keyword search or direct URL (videos, Shorts, playlists, live streams)
- **Audio Download** — MP3 at selectable quality (64–320 kbps)
- **Video Download** — MP4 at selectable quality (144p – 4K)
- **Smart Caching** — downloaded files stored for 1 hour; repeat requests are instant
- **Cookie Support** — bypass age-restrictions via Netscape `.txt`, JSON, or raw `Cookie:` header string
- **Branded filenames** — all files named `title_by_me.gifted.co.ke.mp3/mp4`
- **Keyword → URL** — pass a search keyword to the download endpoints and get the first match automatically

---

## Quick Start (Local)

### Prerequisites

- Python 3.10+
- `ffmpeg` installed and in PATH
- `pip` or a virtual environment

### Installation

```bash
git clone https://github.com/mauricegift/ytdlp-api.git
cd ytdlp-api

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Run the development server

```bash
python app.py
```

Or with Gunicorn (production-like):

```bash
gunicorn --workers 4 --timeout 600 --bind 0.0.0.0:5000 app:app
```

The API is now at `http://localhost:5000`.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Port to listen on |
| `HOST` | `0.0.0.0` | Bind address |
| `DEBUG` | `false` | Enable Flask debug mode |
| `CACHE_DIR` | `/tmp/ytdlp_cache` | Directory for cached files |
| `CACHE_TTL` | `3600` | File cache lifetime in seconds (1 hour) |
| `COOKIES_FILE` | _(auto-detect)_ | Path to cookies file (see Cookies section) |
| `YTDLP_CONCURRENT_FRAGMENTS` | `4` | Parallel fragment downloads (speed) |

---

## API Reference

All successful responses follow:

```json
{ "status": "ok", "data": ..., "count": ..., "elapsed_seconds": 0.123 }
```

All error responses:

```json
{ "status": "error", "message": "..." }
```

---

### `GET /`

Returns API documentation and a list of all endpoints.

---

### `GET /api/health`

Returns server health and cache statistics.

```bash
curl https://ytdlp.gifted.co.ke/api/health
```

---

### `GET /api/search`

Search YouTube or resolve a direct URL.

| Param | Required | Default | Description |
|---|---|---|---|
| `q` | ✅ | — | Search keyword **or** YouTube URL |
| `limit` | ❌ | `10` | Max results (1–50) |
| `cookies` | ❌ | — | Cookie data (see Cookies section) |

```bash
# Keyword search
curl "https://ytdlp.gifted.co.ke/api/search?q=lofi+hip+hop&limit=5"

# Direct URL
curl "https://ytdlp.gifted.co.ke/api/search?q=https://youtu.be/dQw4w9WgXcQ"

# YouTube Shorts
curl "https://ytdlp.gifted.co.ke/api/search?q=https://www.youtube.com/shorts/abc123"
```

**Response fields per result:**

```json
{
  "id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "uploader": "Rick Astley",
  "duration": 213,
  "duration_string": "03:33",
  "view_count": 1770000000,
  "thumbnail": "https://i.ytimg.com/...",
  "live_status": null,
  "is_live": false,
  "upload_date": "20091025"
}
```

---

### `GET /api/info`

Full metadata for a single video.

| Param | Required | Description |
|---|---|---|
| `url` | ✅ | YouTube video URL |
| `cookies` | ❌ | Cookie data |

```bash
curl "https://ytdlp.gifted.co.ke/api/info?url=https://youtu.be/dQw4w9WgXcQ"
```

---

### `GET /api/formats`

List all available download formats for a video.

| Param | Required | Description |
|---|---|---|
| `url` | ✅ | YouTube video URL |
| `cookies` | ❌ | Cookie data |

```bash
curl "https://ytdlp.gifted.co.ke/api/formats?url=https://youtu.be/dQw4w9WgXcQ"
```

---

### `GET /api/download/audio`

Download a YouTube video as an **MP3** file.

| Param | Required | Default | Description |
|---|---|---|---|
| `url` | ✅ | — | YouTube URL **or** search keyword |
| `quality` | ❌ | `best` | `best` (320k), `high` (256k), `medium` (192k), `low` (128k), `worst` (64k), or raw kbps e.g. `192` |
| `cookies` | ❌ | — | Cookie data |

```bash
# Best quality (320kbps)
curl -OJ "https://ytdlp.gifted.co.ke/api/download/audio?url=https://youtu.be/dQw4w9WgXcQ"

# 192kbps
curl -OJ "https://ytdlp.gifted.co.ke/api/download/audio?url=https://youtu.be/dQw4w9WgXcQ&quality=medium"

# By keyword — downloads the first search result
curl -OJ "https://ytdlp.gifted.co.ke/api/download/audio?url=rick+astley+never+gonna+give+you+up"
```

Filename: `Rick_Astley_-_Never_Gonna_Give_You_Up_by_me.gifted.co.ke.mp3`

---

### `GET /api/download/video`

Download a YouTube video as an **MP4** file.

| Param | Required | Default | Description |
|---|---|---|---|
| `url` | ✅ | — | YouTube URL **or** search keyword |
| `quality` | ❌ | `720p` | `best`, `4k`, `1080p`, `720p`, `480p`, `360p`, `240p`, `144p`, `worst` |
| `cookies` | ❌ | — | Cookie data |

```bash
# 720p (default)
curl -OJ "https://ytdlp.gifted.co.ke/api/download/video?url=https://youtu.be/dQw4w9WgXcQ"

# 1080p
curl -OJ "https://ytdlp.gifted.co.ke/api/download/video?url=https://youtu.be/dQw4w9WgXcQ&quality=1080p"

# YouTube Shorts
curl -OJ "https://ytdlp.gifted.co.ke/api/download/video?url=https://www.youtube.com/shorts/abc123"

# By keyword
curl -OJ "https://ytdlp.gifted.co.ke/api/download/video?url=funny+cats&quality=480p"
```

---

### `GET /api/cache/stats`

Returns current cache statistics.

```bash
curl https://ytdlp.gifted.co.ke/api/cache/stats
```

---

### `DELETE /api/cache/clear`

Manually evict all expired cache entries.

```bash
curl -X DELETE https://ytdlp.gifted.co.ke/api/cache/clear
```

---

## Cookies

Some videos require authentication (age-restricted, members-only, etc.).  
Pass cookie data in **any** of these formats:

### 1. Netscape `cookies.txt`

Export from your browser (e.g., using the [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) extension).

Place the file as `cookies.txt` in the project root — it will be auto-detected.

Or pass it via query param:

```bash
curl "https://ytdlp.gifted.co.ke/api/download/audio?url=...&cookies=$(cat cookies.txt | urlencode)"
```

### 2. JSON format

```bash
# Flat dict
curl "...?cookies=%7B%22VISITOR_INFO1_LIVE%22%3A%22abc123%22%7D"

# Or list of cookie objects (browser export)
curl "...?cookies=<url-encoded JSON array>"
```

### 3. Cookie header string

```bash
curl -H "X-Cookies: VISITOR_INFO1_LIVE=abc123; YSC=xyz" \
     "https://ytdlp.gifted.co.ke/api/download/audio?url=..."
```

Or via query param:

```bash
curl "...?cookies=VISITOR_INFO1_LIVE%3Dabc123%3B+YSC%3Dxyz"
```

---

## Project Structure

```
ytdlp-api/
├── app.py              # Main Flask application + all API routes
├── config.py           # All configuration (env-overridable)
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── lib/
│   ├── __init__.py     # Package documentation
│   ├── cache.py        # File cache with 1-hour TTL + background cleaner
│   ├── cookies.py      # Cookie format parsing (Netscape / JSON / header)
│   ├── downloader.py   # yt-dlp audio & video download wrappers
│   ├── searcher.py     # YouTube search and video info
│   └── utils.py        # Filename sanitisation, formatting helpers
└── deploy/
    ├── nginx.conf          # Nginx reverse-proxy config
    ├── ytdlp-api.service   # systemd service unit
    └── setup.sh            # One-shot VPS setup script
```

---

## VPS Deployment

The included `deploy/setup.sh` sets up a fresh Ubuntu/Debian VPS:

```bash
# On your local machine — copy files to VPS
rsync -avz --exclude='.git' --exclude='venv' . root@YOUR_VPS_IP:/opt/ytdlp-api/

# SSH in and run setup
ssh root@YOUR_VPS_IP "bash /opt/ytdlp-api/deploy/setup.sh"
```

This installs Python, ffmpeg, Nginx, creates a systemd service, and starts everything automatically.

---

## License

MIT — do whatever you want, just keep the spirit of open source alive.

---

*Built with yt-dlp, Flask, and ffmpeg. Branded files: `_by_me.gifted.co.ke`*
