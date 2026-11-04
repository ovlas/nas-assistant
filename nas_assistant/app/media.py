"""Photos and videos: thumbnails and the dated index behind the gallery.

Thumbnails and the index live on the NAS disk (.nas_assistant/), so they
travel with the disk and never grow Home Assistant backups.
"""

import hashlib
import io
import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException
from PIL import Image, ImageOps

from . import disks, storage
from .kinds import media_kind as kind_of
from .auth import User

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()  # iPhone HEIC photos
except ImportError:
    pass

THUMB_SIZES = {"s": 400, "l": 1600}
EXIF_IFD = 0x8769
EXIF_DATE_TAGS = (36867, 36868)  # DateTimeOriginal, DateTimeDigitized
TIFF_DATE_TAG = 306  # DateTime


def _meta_dir() -> Path:
    path = disks.NAS_ROOT / ".nas_assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- Thumbnails ---------------------------------------------------------------

def _video_frame(src: Path) -> Image.Image:
    for seek in ("1", "0"):
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", seek, "-i", str(src), "-frames:v", "1",
             "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=60,
        )
        if result.stdout:
            return Image.open(io.BytesIO(result.stdout))
    raise HTTPException(415, "Can't read the video")


def thumb_path(src: Path, size: str) -> Path:
    """Where the thumbnail of this version of the file is cached."""
    if size not in THUMB_SIZES or not src.is_file():
        raise HTTPException(404, "Thumbnail not available")
    if not kind_of(src.name):
        raise HTTPException(415, "Unsupported format")
    stat = src.stat()
    key = hashlib.sha1(f"{src}|{stat.st_mtime_ns}|{stat.st_size}|{size}".encode()).hexdigest()
    return _meta_dir() / "thumbs" / key[:2] / f"{key}.webp"


def make_thumbnail(src: Path, size: str, out: Path) -> Path:
    """Decode and shrink the image or a video frame. Slow: call it from a worker thread."""
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        img = _video_frame(src) if kind_of(src.name) == "video" else ImageOps.exif_transpose(Image.open(src))
        img.thumbnail((THUMB_SIZES[size],) * 2)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        partial = out.with_suffix(f".{os.getpid()}.part")
        img.save(partial, "WEBP", quality=80, method=4)
        os.replace(partial, out)
    except (OSError, SyntaxError, ValueError, ZeroDivisionError, subprocess.TimeoutExpired, Image.DecompressionBombError):
        # Odd files really do these: broken EXIF data can divide by zero while decoding.
        raise HTTPException(415, "Can't create the thumbnail")
    return out


# --- Dated index for the gallery ---------------------------------------------

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_meta_dir() / "index.db", timeout=30)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS media (path TEXT PRIMARY KEY, mtime_ns INTEGER, "
        "size INTEGER, taken INTEGER, kind TEXT)"
    )
    return conn


def _parse_exif_date(value) -> Optional[int]:
    try:
        return int(datetime.strptime(str(value).strip()[:19], "%Y:%m:%d %H:%M:%S").timestamp())
    except ValueError:
        return None


def _taken(path: Path, kind: str, mtime: float) -> int:
    """When the photo/video was shot; falls back to the file date."""
    try:
        if kind == "image":
            with Image.open(path) as img:
                exif = img.getexif()
                tags = exif.get_ifd(EXIF_IFD)
                for value in [*(tags.get(t) for t in EXIF_DATE_TAGS), exif.get(TIFF_DATE_TAG)]:
                    if value and _parse_exif_date(value):
                        return _parse_exif_date(value)
        else:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format_tags=creation_time",
                 "-of", "default=nw=1:nk=1", str(path)],
                capture_output=True, text=True, timeout=30,
            ).stdout.strip()
            if out:
                return int(datetime.fromisoformat(out.replace("Z", "+00:00")).timestamp())
    except (OSError, SyntaxError, ValueError, subprocess.TimeoutExpired):
        pass
    return int(mtime)


# Reading when a photo was shot opens the file: for thousands of new photos (a disk
# that joins the NAS) that is done in the background, and meanwhile the file date is used.
_pending: Dict[str, tuple] = {}
_indexer_lock = threading.Lock()
_indexer: Optional[threading.Thread] = None


def _index_pending() -> None:
    global _indexer
    while True:
        with _indexer_lock:
            if not _pending:
                _indexer = None
                return
            key, (kind, mtime_ns, size) = _pending.popitem()
        taken = _taken(Path(key), kind, mtime_ns / 1e9)
        conn = _db()
        try:
            conn.execute("INSERT OR REPLACE INTO media VALUES (?, ?, ?, ?, ?)", (key, mtime_ns, size, taken, kind))
            conn.commit()
        except sqlite3.Error:
            pass
        finally:
            conn.close()


def _index_later(key: str, kind: str, mtime_ns: int, size: int) -> None:
    global _indexer
    with _indexer_lock:
        _pending[key] = (kind, mtime_ns, size)
        if _indexer is None:
            _indexer = threading.Thread(target=_index_pending, daemon=True)
            _indexer.start()


def with_created(entries: List[dict]) -> List[dict]:
    """Add each entry's creation date: when a photo or video was shot (from the gallery
    index), else the file's own date. Drops the internal "_full" path."""
    keys = [e["_full"] for e in entries if e.get("_full") and kind_of(e["name"])]
    taken = {}
    if keys:
        conn = _db()
        try:
            for i in range(0, len(keys), 500):
                part = keys[i:i + 500]
                taken.update(conn.execute(f"SELECT path, taken FROM media WHERE path IN ({','.join('?' * len(part))})",
                                          part).fetchall())
        finally:
            conn.close()
    for entry in entries:
        entry["created"] = taken.get(entry.pop("_full", None), entry.get("modified", 0))
    return entries


# The gallery list of a space is kept a few seconds: the page asks for it a page at a time.
GALLERY_SECONDS = 20
_galleries: Dict[tuple, tuple] = {}  # (user, space) -> (when, items, full paths)


def gallery(user: User, space: str) -> List[dict]:
    """Every photo and video of a space, newest first (items are shared: don't change them)."""
    return _gallery(user, space)[0]


def _gallery(user: User, space: str) -> tuple:
    cached = _galleries.get((user.id, space))
    if cached and time.monotonic() - cached[0] < GALLERY_SECONDS:
        return cached[1], cached[2]
    items, fulls = _scan_gallery(user, space)
    _galleries[(user.id, space)] = (time.monotonic(), items, fulls)
    return items, fulls


def _scan_gallery(user: User, space: str) -> tuple:
    conn = _db()
    try:
        prefixes = tuple(str(root) + os.sep for _, root in storage.roots(user, space))
        known = {path: (mtime, size, taken) for path, mtime, size, taken in
                 conn.execute("SELECT path, mtime_ns, size, taken FROM media").fetchall()
                 if path.startswith(prefixes)}
        items = []
        seen = set()
        for folder, name, size, mtime_ns, rel, _ in storage._files(user, space):
            kind = kind_of(name)
            if not kind:
                continue
            key = os.path.join(folder, name)
            seen.add(key)
            row = known.get(key)
            if row and row[0] == mtime_ns and row[1] == size:
                taken = row[2]
            else:
                taken = mtime_ns // 10**9  # until the background reads the real date
                _index_later(key, kind, mtime_ns, size)
            items.append(({
                "path": rel,
                "name": name,
                "kind": kind,
                "taken": taken,
                "size": size,
                "v": mtime_ns,
            }, key))
        # Forget files that were deleted or moved.
        gone = [(path,) for path in known if path not in seen]
        if gone:
            conn.executemany("DELETE FROM media WHERE path = ?", gone)
            conn.commit()
    finally:
        conn.close()
    items.sort(key=lambda pair: pair[0]["taken"], reverse=True)
    return [item for item, _ in items], [full for _, full in items]


# --- Thumbnails made ahead --------------------------------------------------------
#
# Making a thumbnail means reading the whole photo (from a USB disk, maybe) and decoding it
# (HEIC is slow): done when the gallery shows it, the page waits. So when a gallery is
# opened, its thumbnails are made in the background, newest first, one at a time.

_ahead: List[str] = []
_ahead_known: set = set()
_ahead_lock = threading.Lock()
_ahead_worker: Optional[threading.Thread] = None


def prepare_thumbs(user: User, space: str) -> None:
    global _ahead_worker
    _, fulls = _gallery(user, space)
    with _ahead_lock:
        fresh = [f for f in fulls if f not in _ahead_known]
        _ahead_known.update(fresh)
        _ahead.extend(fresh)
        if _ahead and _ahead_worker is None:
            _ahead_worker = threading.Thread(target=_make_ahead, daemon=True)
            _ahead_worker.start()


def _make_ahead() -> None:
    global _ahead_worker
    while True:
        with _ahead_lock:
            if not _ahead:
                _ahead_worker = None
                return
            full = _ahead.pop(0)
        try:
            src = Path(full)
            out = thumb_path(src, "s")
            if not out.exists():
                make_thumbnail(src, "s", out)
                time.sleep(0.02)  # leave room for the pages being browsed
        except Exception:  # a file gone or unreadable: skip it
            continue
