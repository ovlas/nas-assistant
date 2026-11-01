"""File types, used to catalogue files and pick thumbnails and icons."""

import os
from typing import Optional

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp"}
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".wma", ".aiff"}
DOCUMENT_EXT = {
    ".pdf", ".txt", ".md", ".rtf", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".pages", ".numbers", ".key", ".epub",
}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".dmg", ".iso"}

KINDS = {
    "image": IMAGE_EXT, "video": VIDEO_EXT, "audio": AUDIO_EXT,
    "document": DOCUMENT_EXT, "archive": ARCHIVE_EXT,
}


def kind_of(name: str) -> str:
    """image, video, audio, document, archive or other."""
    ext = os.path.splitext(name)[1].lower()
    return next((kind for kind, exts in KINDS.items() if ext in exts), "other")


def media_kind(name: str) -> Optional[str]:
    """image or video when the file can have a thumbnail, else None."""
    kind = kind_of(name)
    return kind if kind in ("image", "video") else None
