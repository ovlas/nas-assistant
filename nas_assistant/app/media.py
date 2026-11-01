"""Photos and videos: thumbnails and the dated index behind the gallery.

Thumbnails and the index live on the NAS disk (.nas_assistant/), so they
travel with the disk and never grow Home Assistant backups.
"""

import hashlib
import io
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException
from PIL import Image, ImageOps

from . import disks, storage
from .auth import User

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()  # iPhone HEIC photos
except ImportError:
    pass

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp"}
THUMB_SIZES = {"s": 400, "l": 1600}
EXIF_IFD = 0x8769
EXIF_DATE_TAGS = (36867, 36868)  # DateTimeOriginal, DateTimeDigitized
TIFF_DATE_TAG = 306  # DateTime


def kind_of(name: str) -> Optional[str]:
    ext = os.path.splitext(name)[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    return None


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
    except (OSError, SyntaxError, subprocess.TimeoutExpired):
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


def gallery(user: User, space: str) -> List[dict]:
    root = storage.resolve(user, space, "")
    items = []
    seen = set()
    conn = _db()
    try:
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                kind = kind_of(name)
                if not kind or name.startswith("."):
                    continue
                full = Path(folder) / name
                stat = full.stat()
                key = str(full)
                seen.add(key)
                row = conn.execute("SELECT mtime_ns, size, taken FROM media WHERE path = ?", (key,)).fetchone()
                if row and row[0] == stat.st_mtime_ns and row[1] == stat.st_size:
                    taken = row[2]
                else:
                    taken = _taken(full, kind, stat.st_mtime)
                    conn.execute("INSERT OR REPLACE INTO media VALUES (?, ?, ?, ?, ?)",
                                 (key, stat.st_mtime_ns, stat.st_size, taken, kind))
                items.append({
                    "path": str(full.relative_to(root)),
                    "name": name,
                    "kind": kind,
                    "taken": taken,
                    "size": stat.st_size,
                    "v": stat.st_mtime_ns,
                })
        # Forget files that were deleted or moved.
        prefix = str(root) + os.sep
        for (path,) in conn.execute("SELECT path FROM media WHERE path LIKE ?", (prefix + "%",)).fetchall():
            if path not in seen:
                conn.execute("DELETE FROM media WHERE path = ?", (path,))
        conn.commit()
    finally:
        conn.close()
    items.sort(key=lambda i: i["taken"], reverse=True)
    return items
