"""File storage on the dedicated NAS disk.

An optional extra-storage disk adds room: it appears as one more folder (named
after the disk) at the top of every space, with the same per-user privacy.

Layout under NAS_ROOT, and the same under <extra disk>/NAS Assistant/:
    users/<ha_user_id>/    private space of each user
    family/                shared with every user
    .trash/<ha_user_id>/   deleted items, per user ("Recently deleted")
        <id>/<name>           the item itself
        <id>/.nas_trash.json  where it came from and when it was deleted
"""

import heapq
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import BinaryIO, List, Optional, Tuple

from fastapi import HTTPException

from . import disks
from .auth import User
from .kinds import KINDS, kind_of

NAS_ROOT = disks.NAS_ROOT
CHUNK = 1024 * 1024
SPACES = ("personal", "family")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
TRASH_INFO = ".nas_trash.json"
# Items older than this are deleted for good; 0 keeps them until the trash is emptied.
TRASH_DAYS = int(os.environ.get("NAS_TRASH_DAYS", "30"))
# The extra-storage disk, if any: only its "NAS Assistant" folder is used.
EXTRA_STATE = os.environ.get("NAS_STORAGE_STATE", "none")
EXTRA_NAME = os.environ.get("NAS_STORAGE_NAME", "") or "Extra disk"
EXTRA_DATA = Path(os.environ.get("NAS_STORAGE_ROOT", "/storage")) / "NAS Assistant"


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


def _extra_root(user: User, space: str) -> Optional[Path]:
    if EXTRA_STATE != "mounted":
        return None
    _space_root(user, space)  # validates user and space
    root = EXTRA_DATA / ("users/" + user.id if space == "personal" else "family")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def roots(user: User, space: str) -> List[Tuple[str, Path]]:
    """Where a space lives: ("", NAS disk folder) and, with an extra disk, (EXTRA_NAME, its folder)."""
    found = [("", _space_root(user, space).resolve())]
    extra = _extra_root(user, space)
    if extra:
        found.append((EXTRA_NAME, extra))
    return found


def resolve(user: User, space: str, rel_path: str) -> Path:
    """Map a user-supplied path to a real path, refusing anything outside the space.
    Paths starting with the extra disk's folder name lead to the extra disk."""
    _require_disk()
    rel = rel_path.strip("/")
    first, _, rest = rel.partition("/")
    extra = _extra_root(user, space)
    if extra and first == EXTRA_NAME:
        root, rel = extra, rest
    else:
        root = _space_root(user, space).resolve()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(400, "Invalid path")
    return target


def to_rel(user: User, space: str, full: Path) -> str:
    """The path the web UI uses for a real path (the reverse of resolve)."""
    for prefix, root in sorted(roots(user, space), key=lambda r: -len(str(r[1]))):
        if full == root or root in full.parents:
            rel = str(full.relative_to(root)) if full != root else ""
            return "/".join(p for p in (prefix, rel) if p and p != ".")
    raise HTTPException(400, "Invalid path")


def _walk(user: User, space: str):
    """os.walk over every disk of a space, skipping hidden folders: yields (folder, files)."""
    for _, root in roots(user, space):
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            yield Path(folder), files


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
    extra = _extra_root(user, space)
    if extra and not rel_path.strip("/"):
        stat = extra.stat()
        entries = [e for e in entries if e["name"] != EXTRA_NAME]
        entries.append({"name": EXTRA_NAME, "is_dir": True, "size": 0, "modified": int(stat.st_mtime),
                        "v": stat.st_mtime_ns, "kind": None, "volume": True})
    entries.sort(key=lambda e: (not e["is_dir"], not e.get("volume"), e["name"].lower()))
    return entries


def recent_files(user: User, space: str, limit: int, skip_kinds=()) -> List[dict]:
    """The most recently changed files of a space, newest first."""
    found = []
    for folder, files in _walk(user, space):
        for name in files:
            kind = kind_of(name)
            if name.startswith(".") or kind in skip_kinds:
                continue
            full = folder / name
            stat = full.stat()
            found.append((stat.st_mtime_ns, full, stat, kind))
    entries = []
    for _, full, stat, kind in heapq.nlargest(limit, found, key=lambda f: f[0]):
        entries.append({
            "name": full.name,
            "path": to_rel(user, space, full),
            "is_dir": False,
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
            "v": stat.st_mtime_ns,
            "kind": kind,
        })
    return entries


def trash_count(user: User) -> int:
    return sum(1 for slot in _trash_root(user).iterdir() if not slot.name.startswith("."))


def files_by_kind(user: User, space: str, kind: str) -> List[dict]:
    """Every file of one type in the whole space, newest first."""
    if kind not in KINDS and kind != "other":
        raise HTTPException(400, "Unknown type")
    found = []
    for folder, files in _walk(user, space):
        for name in files:
            if name.startswith(".") or kind_of(name) != kind:
                continue
            full = folder / name
            stat = full.stat()
            found.append({
                "name": name,
                "path": to_rel(user, space, full),
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
    if src in {root for _, root in roots(user, space)}:
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
    return {"path": to_rel(user, to_space, dst)}


# --- Trash ("Recently deleted") ---------------------------------------------

def _trash_root(user: User) -> Path:
    _require_disk()
    if not _SAFE_ID.match(user.id):
        raise HTTPException(400, "Invalid user ID")
    root = NAS_ROOT / ".trash" / user.id
    root.mkdir(parents=True, exist_ok=True)
    return root


def move_to_trash(user: User, space: str, rel_path: str) -> str:
    """Move an item to Recently deleted; returns its trash id (for undo)."""
    target = resolve(user, space, rel_path)
    if target in {root for _, root in roots(user, space)}:
        raise HTTPException(400, "Can't delete the root folder")
    if not target.exists():
        raise HTTPException(404, "Not found")
    slot = _trash_root(user) / str(time.time_ns())
    slot.mkdir()
    shutil.move(str(target), str(slot / target.name))  # same disk: instant
    (slot / TRASH_INFO).write_text(json.dumps({
        "name": target.name,
        "space": space,
        "path": to_rel(user, space, target),
        "deleted": int(time.time()),
    }))
    return slot.name


def _trash_item(user: User, item_id: str) -> Path:
    trash = _trash_root(user)
    slot = trash / item_id
    if item_id.startswith(".") or slot.resolve().parent != trash.resolve() or not slot.exists():
        raise HTTPException(404, "Not found")
    return slot


def _trash_info(slot: Path) -> dict:
    """What a trash entry holds. Entries made before 0.7 are plain "<time>_<name>" files."""
    info_file = slot / TRASH_INFO
    if slot.is_dir() and info_file.is_file():
        info = json.loads(info_file.read_text())
        info["item"] = slot / info["name"]
        return info
    stamp, _, name = slot.name.partition("_")
    return {
        "name": name or slot.name,
        "space": "personal",
        "path": name or slot.name,
        "deleted": int(stamp) if stamp.isdigit() else int(slot.stat().st_mtime),
        "item": slot,
    }


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _erase(slot: Path) -> None:
    if slot.is_dir():
        shutil.rmtree(slot)
    else:
        slot.unlink()


def list_trash(user: User) -> List[dict]:
    items = []
    expired = time.time() - TRASH_DAYS * 86400
    for slot in _trash_root(user).iterdir():
        if slot.name.startswith("."):
            continue
        info = _trash_info(slot)
        if TRASH_DAYS and info["deleted"] < expired:
            _erase(slot)
            continue
        item = info["item"]
        if not item.exists():
            continue
        is_dir = item.is_dir()
        items.append({
            "id": slot.name,
            "name": info["name"],
            "space": info["space"],
            "path": info["path"],
            "deleted": info["deleted"],
            "expires": info["deleted"] + TRASH_DAYS * 86400 if TRASH_DAYS else None,
            "is_dir": is_dir,
            "size": _size(item),
            "kind": None if is_dir else kind_of(info["name"]),
            "v": item.stat().st_mtime_ns,
        })
    items.sort(key=lambda i: i["deleted"], reverse=True)
    return items


def trash_file(user: User, item_id: str) -> Path:
    """The deleted file itself, for thumbnails."""
    return _trash_info(_trash_item(user, item_id))["item"]


def _free_name(folder: Path, name: str) -> Path:
    """name, or "name (2).ext", "name (3).ext"… if it is taken."""
    target = folder / name
    stem, ext = os.path.splitext(name) if not name.startswith(".") else (name, "")
    n = 2
    while target.exists():
        target = folder / f"{stem} ({n}){ext}"
        n += 1
    return target


def restore(user: User, item_id: str) -> dict:
    """Put an item back where it was, recreating its folders if needed."""
    slot = _trash_item(user, item_id)
    info = _trash_info(slot)
    space = info["space"] if info["space"] in SPACES else "personal"
    parent = os.path.dirname(info["path"])
    folder = resolve(user, space, parent)
    folder.mkdir(parents=True, exist_ok=True)
    target = _free_name(folder, info["name"])
    shutil.move(str(info["item"]), str(target))
    if slot.exists():
        _erase(slot)
    return {"space": space, "path": to_rel(user, space, target)}


def delete_forever(user: User, item_id: str) -> None:
    _erase(_trash_item(user, item_id))


def empty_trash(user: User) -> None:
    for slot in _trash_root(user).iterdir():
        if not slot.name.startswith("."):
            _erase(slot)


def usage() -> dict:
    _require_disk()
    total, used, free = shutil.disk_usage(NAS_ROOT)
    return {"total": total, "used": used, "free": free}
