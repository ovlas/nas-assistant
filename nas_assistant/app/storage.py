"""File storage: one space for every user, spread over the NAS disk and the
optional extra-storage disk, which are pooled together.

Files of all disks appear together, in the same folders, like one bigger disk.
A folder can exist on both disks; new files go where their folder already is,
or to the disk with more free space. Moving within a disk is instant; between
disks the file is copied, then removed.

Each disk keeps NAS Assistant's folders where it finds them, so a disk can
change role (NAS disk, extra storage) and its files are always there:
- at the top of the disk (a disk that was a NAS disk), or
- in a "NAS Assistant" folder (a disk first used as extra storage, so the
  rest of what is on it stays apart).

Layout in each disk's data folder:
    users/<ha_user_id>/    private space of each user
    family/                shared with every user
    .trash/<ha_user_id>/   deleted items of that disk, per user ("Recently deleted")
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
from typing import BinaryIO, List, Tuple

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
DATA_FOLDER = "NAS Assistant"
EXTRA_STATE = os.environ.get("NAS_STORAGE_STATE", "none")
EXTRA_MOUNT = Path(os.environ.get("NAS_STORAGE_ROOT", "/storage"))
# Paths saved by versions before the pool started with the extra disk's name.
EXTRA_NAME = os.environ.get("NAS_STORAGE_NAME", "") or "Extra disk"


def data_root(mount: Path, fresh: Path) -> Path:
    """Where NAS Assistant's folders are on a disk; `fresh` for a disk never used yet."""
    sub = mount / DATA_FOLDER
    if (sub / "users").is_dir() or (sub / "family").is_dir():
        return sub
    if (mount / "users").is_dir() or (mount / "family").is_dir():
        return mount
    return fresh


def disk_roots() -> List[Path]:
    """Data folder of each disk in the pool, the NAS disk first."""
    found = [data_root(NAS_ROOT, NAS_ROOT)]
    if EXTRA_STATE == "mounted":
        found.append(data_root(EXTRA_MOUNT, EXTRA_MOUNT / DATA_FOLDER))
    return found


def _require_disk() -> None:
    if disks.state() != "mounted":
        # Never fall back to the main disk.
        raise HTTPException(503, "NAS disk not available")


def _check_space(user: User, space: str) -> str:
    if not _SAFE_ID.match(user.id):
        raise HTTPException(400, "Invalid user ID")
    if space not in SPACES:
        raise HTTPException(400, "Unknown space")
    return "users/" + user.id if space == "personal" else "family"


def _space_root(user: User, space: str) -> Path:
    """The space's folder on the NAS disk (always there)."""
    root = disk_roots()[0] / _check_space(user, space)
    root.mkdir(parents=True, exist_ok=True)
    return root


def roots(user: User, space: str) -> List[Tuple[str, Path]]:
    """The space's folder on every disk of the pool: [("", path), …], the NAS disk first."""
    sub = _check_space(user, space)
    _space_root(user, space)
    return [("", (root / sub).resolve()) for root in disk_roots() if (root / sub).is_dir()]


def _inside(root: Path, rel: str) -> Path:
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(400, "Invalid path")
    return target


def _free(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0


def candidates(user: User, space: str, rel_path: str) -> List[Path]:
    """Where a path exists, on each disk of the pool (a folder can be on several)."""
    _require_disk()
    rel = rel_path.strip("/")
    found = [p for _, root in roots(user, space) for p in [_inside(root, rel)] if os.path.lexists(p)]
    if not found and EXTRA_STATE == "mounted":
        # A path saved before the pool, starting with the extra disk's name.
        first, _, rest = rel.partition("/")
        extra = data_root(EXTRA_MOUNT, EXTRA_MOUNT / DATA_FOLDER) / _check_space(user, space)
        if first == EXTRA_NAME and extra.is_dir():
            target = _inside(extra.resolve(), rest)
            if os.path.lexists(target):
                found = [target]
    return found


def resolve(user: User, space: str, rel_path: str) -> Path:
    """Map a path of the web UI to a real path, refusing anything outside the space.
    An existing path is found on whichever disk has it; a new one goes where its
    parent folder already is, or else to the disk with the most free space."""
    found = candidates(user, space, rel_path)
    if found:
        return found[0]
    rel = rel_path.strip("/")
    pool = roots(user, space)
    parent = os.path.dirname(rel)
    with_parent = [root for _, root in pool if not parent or (root / parent).is_dir()]
    choice = max(with_parent or [root for _, root in pool], key=_free)
    return _inside(choice, rel)


def to_rel(user: User, space: str, full: Path) -> str:
    """The path the web UI uses for a real path (the reverse of resolve)."""
    for _, root in sorted(roots(user, space), key=lambda r: -len(str(r[1]))):
        if full == root or root in full.parents:
            rel = str(full.relative_to(root)) if full != root else ""
            return "" if rel == "." else rel
    raise HTTPException(400, "Invalid path")


def _walk(user: User, space: str):
    """os.walk over every disk of a space, skipping hidden folders: yields (folder, files)."""
    for _, root in roots(user, space):
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            yield Path(folder), files


def _clean_rel(path: str) -> str:
    """A stored relative path in one canonical form ("" for the space root)."""
    path = path.strip("/")
    return os.path.normpath(path) if path else ""


def _check_name(name: str) -> str:
    name = name.strip()
    if not name or name in (".", "..") or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "Invalid name")
    return name


def list_dir(user: User, space: str, rel_path: str) -> List[dict]:
    """A folder's content, merged from every disk where the folder exists."""
    folders = [f for f in candidates(user, space, rel_path) if f.is_dir()]
    if not folders:
        if rel_path.strip("/"):
            raise HTTPException(404, "Folder not found")
        folders = [_space_root(user, space)]
    entries = {}
    for folder in folders:
        for entry in os.scandir(folder):
            if entry.name.startswith("."):
                continue
            stat = entry.stat()
            known = entries.get(entry.name)
            if known:  # the same folder on two disks: one entry, latest date
                known["modified"] = max(known["modified"], int(stat.st_mtime))
                continue
            entries[entry.name] = {
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": 0 if entry.is_dir() else stat.st_size,
                "modified": int(stat.st_mtime),
                "v": stat.st_mtime_ns,
                "kind": None if entry.is_dir() else kind_of(entry.name),
            }
    return sorted(entries.values(), key=lambda e: (not e["is_dir"], e["name"].lower()))


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
    return len({slot.name for trash in _trash_roots(user) for slot in trash.iterdir() if not slot.name.startswith(".")})


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
    rel = os.path.join(rel_path.strip("/"), _check_name(name))
    if candidates(user, space, rel):
        raise HTTPException(409, "Already exists")
    resolve(user, space, rel).mkdir(parents=True)


def save_file(user: User, space: str, rel_path: str, name: str, data: BinaryIO) -> dict:
    target = resolve(user, space, os.path.join(rel_path.strip("/"), _check_name(name)))
    folder = target.parent
    folder.mkdir(parents=True, exist_ok=True)  # e.g. Foto/2026/11 for gallery uploads
    # Write to a hidden temp file first so a dropped upload never leaves a broken file.
    partial = folder / f".{target.name}.part"
    with open(partial, "wb") as out:
        shutil.copyfileobj(data, out, CHUNK)
    os.replace(partial, target)
    return {"name": target.name, "size": target.stat().st_size}


def chunk_targets(user: User, space: str, rel_path: str, name: str):
    """Destination of a chunked upload and the hidden file it grows in meanwhile.
    All pieces of an upload go to the same disk: the one where it started."""
    name = _check_name(name)
    rel = rel_path.strip("/")
    started = candidates(user, space, os.path.join(rel, f".{name}.part"))
    target = started[0].parent / name if started else resolve(user, space, os.path.join(rel, name))
    target.parent.mkdir(parents=True, exist_ok=True)
    return target.parent / f".{name}.part", target


def _movable(user: User, space: str, rel_path: str) -> List[Path]:
    """Every copy of an item on the disks (a folder can be on several)."""
    found = candidates(user, space, rel_path)
    if not rel_path.strip("/") or any(p in {root for _, root in roots(user, space)} for p in found):
        raise HTTPException(400, "Can't change the root folder")
    if not found:
        raise HTTPException(404, "Not found")
    return found


def rename(user: User, space: str, rel_path: str, new_name: str) -> dict:
    sources = _movable(user, space, rel_path)
    new_name = _check_name(new_name)
    for src in sources:
        dst = src.parent / new_name
        # A case-only change ("foto.JPG" -> "Foto.jpg") is the same file on NTFS/exFAT.
        if dst.exists() and not os.path.samefile(src, dst):
            raise HTTPException(409, "Already exists")
    for src in sources:
        os.rename(src, src.parent / new_name)
    return {"name": new_name}


def _disk_of(path: Path) -> Path:
    return next(root for root in disk_roots() if root.resolve() in path.parents or path == root.resolve())


def move(user: User, space: str, rel_path: str, to_space: str, to_path: str) -> dict:
    """Move a file or folder to another folder, also between My space and Family.
    On the same disk it is instant; to a folder that only exists on the other disk it is copied."""
    sources = _movable(user, space, rel_path)
    folders = [f for f in candidates(user, to_space, to_path) if f.is_dir()]
    if not folders and not to_path.strip("/"):
        folders = [_space_root(user, to_space)]
    if not folders:
        raise HTTPException(404, "Folder not found")
    name = sources[0].name
    if candidates(user, to_space, os.path.join(to_path.strip("/"), name)):
        raise HTTPException(409, "Already exists")
    dst = None
    for src in sources:
        if src.is_dir() and any(f == src or src in f.parents for f in folders):
            raise HTTPException(400, "Can't move a folder into itself")
        same_disk = [f for f in folders if _disk_of(f) == _disk_of(src)]
        dst = (same_disk or folders)[0] / name
        shutil.move(str(src), str(dst))
    return {"path": to_rel(user, to_space, dst)}


# --- Trash ("Recently deleted") ---------------------------------------------

def _trash_roots(user: User) -> List[Path]:
    """The trash of each disk: deleted items stay on their own disk."""
    _require_disk()
    if not _SAFE_ID.match(user.id):
        raise HTTPException(400, "Invalid user ID")
    found = []
    for disk in disk_roots():
        root = disk / ".trash" / user.id
        root.mkdir(parents=True, exist_ok=True)
        found.append(root)
    return found


def _trash_root(user: User) -> Path:
    return _trash_roots(user)[0]


def move_to_trash(user: User, space: str, rel_path: str) -> str:
    """Move an item to Recently deleted, on the disk it is on; returns its trash id (for undo)."""
    sources = _movable(user, space, rel_path)
    item_id = str(time.time_ns())
    for src in sources:
        disk = _disk_of(src)
        slot = disk / ".trash" / user.id / item_id
        slot.mkdir(parents=True)
        shutil.move(str(src), str(slot / src.name))  # same disk: instant
        (slot / TRASH_INFO).write_text(json.dumps({
            "name": src.name,
            "space": space,
            "path": rel_path.strip("/"),
            "deleted": int(time.time()),
        }))
    return item_id


def _trash_items(user: User, item_id: str) -> List[Path]:
    """The slots of a trash item on every disk."""
    slots = []
    for trash in _trash_roots(user):
        slot = trash / item_id
        if not item_id.startswith(".") and slot.resolve().parent == trash.resolve() and slot.exists():
            slots.append(slot)
    if not slots:
        raise HTTPException(404, "Not found")
    return slots


def _trash_item(user: User, item_id: str) -> Path:
    return _trash_items(user, item_id)[0]


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
    items = {}
    expired = time.time() - TRASH_DAYS * 86400
    for slot in (s for trash in _trash_roots(user) for s in trash.iterdir()):
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
        if slot.name in items:  # a folder that was on both disks: one item
            items[slot.name]["size"] += _size(item)
            continue
        items[slot.name] = ({
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
    return sorted(items.values(), key=lambda i: i["deleted"], reverse=True)


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
    """Put an item back where it was, on its own disk, recreating its folders if needed."""
    target = None
    for slot in _trash_items(user, item_id):
        info = _trash_info(slot)
        space = info["space"] if info["space"] in SPACES else "personal"
        disk = next(d for d in disk_roots() if d.resolve() in slot.parents)
        folder = _inside((disk / _check_space(user, space)).resolve(), os.path.dirname(info["path"]))
        folder.mkdir(parents=True, exist_ok=True)
        target = _free_name(folder, info["name"]) if target is None else folder / target.name
        if target.exists() and info["item"].is_dir():
            # The other half of a folder that was on both disks: merge it back.
            shutil.copytree(info["item"], target, dirs_exist_ok=True)
            shutil.rmtree(info["item"])
        else:
            shutil.move(str(info["item"]), str(target))
        if slot.exists():
            _erase(slot)
    return {"space": space, "path": to_rel(user, space, target)}


def delete_forever(user: User, item_id: str) -> None:
    for slot in _trash_items(user, item_id):
        _erase(slot)


def empty_trash(user: User) -> None:
    for trash in _trash_roots(user):
        for slot in trash.iterdir():
            if not slot.name.startswith("."):
                _erase(slot)


def usage() -> dict:
    """Space of the whole pool: the NAS disk plus the extra-storage disk."""
    _require_disk()
    mounts = [NAS_ROOT] + ([EXTRA_MOUNT] if EXTRA_STATE == "mounted" else [])
    totals = [shutil.disk_usage(m) for m in mounts]
    return {"total": sum(t.total for t in totals), "used": sum(t.used for t in totals),
            "free": sum(t.free for t in totals), "disks": len(totals)}
