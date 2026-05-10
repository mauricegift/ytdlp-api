"""
Cookie handling for yt-dlp.

Supported input formats
-----------------------
1. **Netscape / cookies.txt** — the format yt-dlp uses natively.
   Detected by the presence of ``# Netscape HTTP Cookie File`` header,
   or when the file has a .txt extension.

2. **JSON** — either a flat ``{name: value, ...}`` mapping or a list of
   cookie objects ``[{"name": "...", "value": "...", "domain": "..."}, ...]``.

3. **Header string** — the raw value of an HTTP ``Cookie:`` header,
   e.g. ``session_id=abc123; token=xyz``.

Usage
-----
Pass the result of ``resolve_cookie_file()`` to yt-dlp's ``cookiefile``
option, or pass ``None`` to disable cookie usage.
"""

import json
import os
import re
import tempfile
import time
import logging
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# Default YouTube domain used when building Netscape entries
_YT_DOMAIN = ".youtube.com"

_NETSCAPE_HEADER = "# Netscape HTTP Cookie File\n# https://curl.haxx.se/rfc/cookie_spec.html\n# This is a generated file! Do not edit.\n\n"


# ── Internal converters ────────────────────────────────────────────────────


def _header_string_to_netscape(header: str) -> str:
    """Convert a Cookie: header string to Netscape format."""
    lines = [_NETSCAPE_HEADER]
    now = int(time.time()) + 365 * 86400  # 1-year expiry
    # Strip leading 'Cookie:' if present
    header = re.sub(r"^[Cc]ookie:\s*", "", header.strip())
    for part in header.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        value = value.strip()
        # domain flag path secure expires name value
        lines.append(f"{_YT_DOMAIN}\tTRUE\t/\tFALSE\t{now}\t{name}\t{value}\n")
    return "".join(lines)


def _json_to_netscape(data: str | bytes) -> str:
    """Convert a JSON cookies payload to Netscape format."""
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON cookie data: {exc}") from exc

    lines = [_NETSCAPE_HEADER]
    now = int(time.time()) + 365 * 86400

    if isinstance(parsed, dict):
        # {name: value, ...}
        for name, value in parsed.items():
            lines.append(f"{_YT_DOMAIN}\tTRUE\t/\tFALSE\t{now}\t{name}\t{value}\n")
    elif isinstance(parsed, list):
        # [{name, value, domain?, path?, secure?, expirationDate?}, ...]
        for cookie in parsed:
            domain = cookie.get("domain") or _YT_DOMAIN
            if not domain.startswith("."):
                domain = "." + domain
            path = cookie.get("path", "/")
            secure = "TRUE" if cookie.get("secure") else "FALSE"
            expires = int(cookie.get("expirationDate") or now)
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            if name:
                lines.append(f"{domain}\tTRUE\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
    else:
        raise ValueError("JSON cookies must be a dict or list")

    return "".join(lines)


def _is_netscape(text: str) -> bool:
    return "# Netscape HTTP Cookie File" in text[:200]


# ── Public API ─────────────────────────────────────────────────────────────


def resolve_cookie_file(cookie_input: str | None = None) -> str | None:
    """
    Determine and return the path to a Netscape-format cookies file.

    Priority
    --------
    1. ``cookie_input`` argument (raw text or file path).
    2. ``config.COOKIES_FILE`` (set via env or auto-detected in project root).

    Returns ``None`` when no cookies are configured.
    """
    source = cookie_input or config.COOKIES_FILE or None
    if not source:
        return None

    # If it looks like a file path that actually exists → inspect it
    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        if _is_netscape(content):
            return source  # already Netscape format
        # Try JSON
        try:
            netscape = _json_to_netscape(content)
            return _write_temp_cookies(netscape)
        except ValueError:
            pass
        # Try header string
        netscape = _header_string_to_netscape(content)
        return _write_temp_cookies(netscape)

    # Not a file path — treat as raw text
    text = source.strip()
    if _is_netscape(text):
        return _write_temp_cookies(text)

    # Try JSON
    try:
        netscape = _json_to_netscape(text)
        return _write_temp_cookies(netscape)
    except ValueError:
        pass

    # Fall back to header string format
    netscape = _header_string_to_netscape(text)
    return _write_temp_cookies(netscape)


def _write_temp_cookies(content: str) -> str:
    """Write Netscape cookie content to a temp file and return its path."""
    fd, path = tempfile.mkstemp(prefix="ytdlp_cookies_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    logger.debug("Cookies written to temp file: %s", path)
    return path
