"""File storage on the dedicated NAS disk.

Layout under NAS_ROOT:
    users/<ha_user_id>/    private space of each user
    family/                shared with every user
    .trash/<ha_user_id>/   deleted items, per user
"""

import os
import re
import shutil
import time
from pathlib import Path
from typing import BinaryIO, List

from fastapi import HTTPException

from . import disks
from .auth import User
from .kinds import KINDS, kind_of

NAS_ROOT = disks.NAS_ROOT
CHUNK = 1024 * 1024
SPACES = ("personal", "family")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _require_disk() -> None:
    if disks.state() != "mounted":
        # Never fall back to the main disk.
        raise HTTPException(503, "NAS disk not available")


def _space_root(user: User, space: str) -> Path:
    if not _SAFE_ID.match(user.id):
        raise HTTPException(400, "Invalid user ID")
    if space == "personal":
        root = NAS_ROOT / "users" / user.id
    elif space == "family":
        root = NAS_ROOT / "family"
    else:
        raise HTTPException(400, "Unknown space")
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve(user: User, space: str, rel_path: str) -> Path:
    """Map a user-supplied path to a real path, refusing anything outside the space."""
    _require_disk()
    root = _space_root(user, space).resolve()
    target = (root / rel_path.lstrip("/")).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(400, "Invalid path")
    return target


def _check_name(name: str) -> str:
    name = name.strip()
    if not name or name in (".", "..") or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "Invalid name")
    return name


def list_dir(user: User, space: str, rel_path: str) -> List[dict]:
    folder = resolve(user, space, rel_path)
    if not folder.is_dir():
        raise HTTPException(404, "Folder not found")
    entries = []
    for entry in os.scandir(folder):
        if entry.name.startswith("."):
            continue
        stat = entry.stat()
        entries.append({
            "name": entry.name,
            "is_dir": entry.is_dir(),
            "size": 0 if entry.is_dir() else stat.st_size,
            "modified": int(stat.st_mtime),
            "v": stat.st_mtime_ns,
            "kind": None if entry.is_dir() else kind_of(entry.name),
        })
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries


def files_by_kind(user: User, space: str, kind: str) -> List[dict]:
    """Every file of one type in the whole space, newest first."""
    if kind not in KINDS and kind != "other":
        raise HTTPException(400, "Unknown type")
    root = resolve(user, space, "")
    found = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.startswith(".") or kind_of(name) != kind:
                continue
            full = Path(folder) / name
            stat = full.stat()
            found.append({
                "name": name,
                "path": str(full.relative_to(root)),
                "is_dir": False,
                "size": stat.st_size,
                "modified": int(stat.st_mtime),
                "v": stat.st_mtime_ns,
                "kind": kind,
            })
    found.sort(key=lambda e: e["modified"], reverse=True)
    return found


def make_dir(user: User, space: str, rel_path: str, name: str) -> None:
    target = resolve(user, space, rel_path) / _check_name(name)
    if target.exists():
        raise HTTPException(409, "Already exists")
    target.mkdir()


def save_file(user: User, space: str, rel_path: str, name: str, data: BinaryIO) -> dict:
    folder = resolve(user, space, rel_path)
    folder.mkdir(parents=True, exist_ok=True)  # e.g. Foto/2026/11 for gallery uploads
    target = folder / _check_name(name)
    # Write to a hidden temp file first so a dropped upload never leaves a broken file.
    partial = folder / f".{target.name}.part"
    with open(partial, "wb") as out:
        shutil.copyfileobj(data, out, CHUNK)
    os.replace(partial, target)
    return {"name": target.name, "size": target.stat().st_size}


def chunk_targets(user: User, space: str, rel_path: str, name: str):
    """Destination of a chunked upload and the hidden file it grows in meanwhile."""
    folder = resolve(user, space, rel_path)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / _check_name(name)
    return folder / f".{target.name}.part", target


def _movable(user: User, space: str, rel_path: str) -> Path:
    src = resolve(user, space, rel_path)
    if src == _space_root(user, space).resolve():
        raise HTTPException(400, "Can't change the root folder")
    if not src.exists():
        raise HTTPException(404, "Not found")
    return src


def rename(user: User, space: str, rel_path: str, new_name: str) -> dict:
    src = _movable(user, space, rel_path)
    dst = src.parent / _check_name(new_name)
    # A case-only change ("foto.JPG" -> "Foto.jpg") is the same file on NTFS/exFAT.
    if dst.exists() and not os.path.samefile(src, dst):
        raise HTTPException(409, "Already exists")
    os.rename(src, dst)
    return {"name": dst.name}


def move(user: User, space: str, rel_path: str, to_space: str, to_path: str) -> dict:
    """Move a file or folder to another folder, also between My space and Family."""
    src = _movable(user, space, rel_path)
    folder = resolve(user, to_space, to_path)
    if not folder.is_dir():
        raise HTTPException(404, "Folder not found")
    if src.is_dir() and (folder == src or src in folder.parents):
        raise HTTPException(400, "Can't move a folder into itself")
    dst = folder / src.name
    if dst.exists():
        raise HTTPException(409, "Already exists")
    shutil.move(str(src), str(dst))  # same disk: an instant rename, nothing is copied
    return {"path": str(dst.relative_to(_space_root(user, to_space).resolve()))}


def move_to_trash(user: User, space: str, rel_path: str) -> None:
    target = resolve(user, space, rel_path)
    if target == _space_root(user, space).resolve():
        raise HTTPException(400, "Can't delete the root folder")
    if not target.exists():
        raise HTTPException(404, "Not found")
    trash = NAS_ROOT / ".trash" / user.id
    trash.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target), str(trash / f"{int(time.time())}_{target.name}"))


def usage() -> dict:
    _require_disk()
    total, used, free = shutil.disk_usage(NAS_ROOT)
    return {"total": total, "used": used, "free": free}
