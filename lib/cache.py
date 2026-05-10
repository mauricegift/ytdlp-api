"""
File cache with TTL eviction.

Cached files are stored under CACHE_DIR.
An in-memory index maps cache_key → (file_path, expires_at).
A background daemon thread sweeps expired entries every CACHE_CLEANUP_INTERVAL.
"""

import os
import time
import threading
import logging
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# {cache_key: {"path": str, "expires_at": float}}
_index: dict[str, dict] = {}
_lock = threading.Lock()


def _ensure_cache_dir() -> None:
    Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)


def get(cache_key: str) -> str | None:
    """
    Return the cached file path if it exists and has not expired,
    otherwise return None.
    """
    with _lock:
        entry = _index.get(cache_key)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        logger.debug("Cache expired for key=%s", cache_key)
        _evict(cache_key)
        return None
    path = entry["path"]
    if not os.path.isfile(path):
        logger.warning("Cache entry points to missing file: %s", path)
        _evict(cache_key)
        return None
    logger.info("Cache HIT key=%s path=%s", cache_key, path)
    return path


def put(cache_key: str, file_path: str) -> None:
    """Register a downloaded file in the cache."""
    expires_at = time.time() + config.CACHE_TTL_SECONDS
    with _lock:
        _index[cache_key] = {"path": file_path, "expires_at": expires_at}
    logger.info(
        "Cache SET key=%s path=%s ttl=%ds",
        cache_key,
        file_path,
        config.CACHE_TTL_SECONDS,
    )


def _evict(cache_key: str) -> None:
    """Remove a single entry from the index (and delete file if possible)."""
    with _lock:
        entry = _index.pop(cache_key, None)
    if entry:
        path = entry.get("path", "")
        if path and os.path.isfile(path):
            try:
                os.remove(path)
                logger.debug("Deleted cached file: %s", path)
            except OSError as exc:
                logger.warning("Could not delete %s: %s", path, exc)


def cleanup() -> int:
    """
    Sweep all entries, remove those that have expired.
    Returns the number of entries removed.
    """
    now = time.time()
    expired = []
    with _lock:
        for key, entry in list(_index.items()):
            if now > entry["expires_at"] or not os.path.isfile(entry.get("path", "")):
                expired.append(key)

    for key in expired:
        _evict(key)

    if expired:
        logger.info("Cache cleanup: removed %d expired entries", len(expired))
    return len(expired)


def stats() -> dict:
    """Return current cache statistics."""
    with _lock:
        total = len(_index)
        now = time.time()
        valid = sum(1 for e in _index.values() if now <= e["expires_at"])

    total_bytes = 0
    for entry in list(_index.values()):
        p = entry.get("path", "")
        if p and os.path.isfile(p):
            total_bytes += os.path.getsize(p)

    return {
        "total_entries": total,
        "valid_entries": valid,
        "expired_entries": total - valid,
        "total_size_bytes": total_bytes,
        "cache_dir": config.CACHE_DIR,
        "ttl_seconds": config.CACHE_TTL_SECONDS,
    }


def _background_cleanup() -> None:
    """Daemon thread: run cleanup every CACHE_CLEANUP_INTERVAL seconds."""
    while True:
        time.sleep(config.CACHE_CLEANUP_INTERVAL)
        try:
            cleanup()
        except Exception as exc:  # pragma: no cover
            logger.error("Background cache cleanup failed: %s", exc)


def start() -> None:
    """Initialise the cache directory and launch the background cleaner."""
    _ensure_cache_dir()
    t = threading.Thread(target=_background_cleanup, daemon=True, name="cache-cleaner")
    t.start()
    logger.info("Cache started — dir=%s ttl=%ds", config.CACHE_DIR, config.CACHE_TTL_SECONDS)
