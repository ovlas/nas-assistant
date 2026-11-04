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
from typing import BinaryIO, Dict, List, Tuple

from fastapi import HTTPException

from . import disks
from .auth import User
from . import pieces
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


def _has_folders(root: Path) -> bool:
    return (root / "users").is_dir() or (root / "family").is_dir()


def _has_files(root: Path) -> bool:
    """True if anything visible is in its family folder or in a user's space."""
    def visible(folder: Path) -> bool:
        try:
            return any(not p.name.startswith(".") for p in folder.iterdir())
        except OSError:
            return False
    users = root / "users"
    return visible(root / "family") or (users.is_dir() and any(visible(u) for u in users.iterdir() if u.is_dir()))


_data_roots: Dict[tuple, tuple] = {}


def data_root(mount: Path, fresh: Path) -> Path:
    """Where NAS Assistant's folders are on a disk; `fresh` for a disk never used yet.
    A former NAS disk keeps them at its root; an extra disk in "NAS Assistant/". If both
    exist (e.g. empty folders made by an older version), the one holding files wins.
    Remembered for a few seconds: every request asks, and a USB disk answers slowly."""
    cached = _data_roots.get((mount, fresh))
    if cached and time.monotonic() - cached[0] < 30:
        return cached[1]
    root = _find_data_root(mount, fresh)
    _data_roots[(mount, fresh)] = (time.monotonic(), root)
    return root


def _find_data_root(mount: Path, fresh: Path) -> Path:
    sub = mount / DATA_FOLDER
    if _has_folders(sub) and _has_folders(mount):
        return mount if _has_files(mount) and not _has_files(sub) else sub
    if _has_folders(sub):
        return sub
    if _has_folders(mount):
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


KEEP_FREE = 20 * 1024 ** 3  # past this, new files go to the disk with most room


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
    An existing path is found on whichever disk has it. A new one goes to the NAS disk
    while it has room, even if its folder so far is only on the extra disk (the folder is
    made there too, and the merged view shows one folder): the extra disk may be an old
    USB 2 drive, and writing there crawls. When the NAS disk is nearly full: most room."""
    found = candidates(user, space, rel_path)
    if found:
        return found[0]
    rel = rel_path.strip("/")
    pool = [root for _, root in roots(user, space)]  # the NAS disk comes first
    roomy = [root for root in pool if _free(root) > KEEP_FREE]
    return _inside(roomy[0] if roomy else max(pool, key=_free), rel)


def to_rel(user: User, space: str, full: Path) -> str:
    """The path the web UI uses for a real path (the reverse of resolve)."""
    for _, root in sorted(roots(user, space), key=lambda r: -len(str(r[1]))):
        if full == root or root in full.parents:
            rel = str(full.relative_to(root)) if full != root else ""
            return "" if rel == "." else rel
    raise HTTPException(400, "Invalid path")


# Folder contents remembered by the folder's own date: adding, renaming or deleting a file
# changes it, so a folder is read again only when something in it changed. Walking a big
# disk (tens of thousands of files, maybe on USB 2) then costs one check per folder.
_dir_cache: Dict[str, tuple] = {}


def _listing(folder: str) -> list:
    """(name, is_dir, size, mtime_ns, ctime) of a folder's visible entries."""
    try:
        mtime = os.stat(folder).st_mtime_ns
    except OSError:
        return []
    cached = _dir_cache.get(folder)
    if cached and cached[0] == mtime:
        return cached[1]
    items = []
    try:
        with os.scandir(folder) as found:
            for entry in found:
                if entry.name.startswith("."):
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    stat = entry.stat()
                except OSError:
                    continue
                items.append((entry.name, is_dir, 0 if is_dir else stat.st_size, stat.st_mtime_ns, int(stat.st_ctime)))
    except OSError:
        return []
    _dir_cache[folder] = (mtime, items)
    return items


def _files(user: User, space: str):
    """Every file of a space on every disk: yields (folder, name, size, mtime_ns, rel path, ctime)."""
    for _, root in roots(user, space):
        stack = [(str(root), "")]
        while stack:
            folder, rel = stack.pop()
            for name, is_dir, size, mtime, ctime in _listing(folder):
                if is_dir:
                    stack.append((os.path.join(folder, name), f"{rel}/{name}" if rel else name))
                else:
                    yield folder, name, size, mtime, f"{rel}/{name}" if rel else name, ctime


def warm() -> None:
    """Read every folder once in the background, so the first pages open fast."""
    for root in disk_roots():
        for top in ("users", "family"):
            stack = [str(root / top)]
            while stack:
                folder = stack.pop()
                stack += [os.path.join(folder, n) for n, is_dir, *_ in _listing(folder) if is_dir]


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
                "added": int(stat.st_ctime),  # when it arrived here (an upload, a copy, a move)
                "v": stat.st_mtime_ns,
                "kind": None if entry.is_dir() else kind_of(entry.name),
                "_full": entry.path,  # for the shooting date of photos and videos
            }
    return sorted(entries.values(), key=lambda e: (not e["is_dir"], e["name"].lower()))


def tree_size(folders: List[Path]) -> Tuple[int, int]:
    """(bytes, files) of everything inside these folders (the same folder on several disks).
    Folder listings are cached, so asking again is quick."""
    size = files = 0
    stack = [str(f) for f in folders]
    while stack:
        folder = stack.pop()
        for name, is_dir, length, *_ in _listing(folder):
            if is_dir:
                if not os.path.islink(os.path.join(folder, name)):
                    stack.append(os.path.join(folder, name))
            else:
                size += length
                files += 1
    return size, files


def folder_sizes(folders: List[Path]) -> dict:
    """The size of each sub-folder of a folder, and of the folder itself."""
    subs: Dict[str, List[Path]] = {}
    for folder in folders:
        for name, is_dir, *_ in _listing(str(folder)):
            if is_dir:
                subs.setdefault(name, []).append(folder / name)
    sizes = {}
    for name, paths in subs.items():
        size, files = tree_size(paths)
        sizes[name] = {"size": size, "files": files}
    total, count = tree_size(folders)
    return {"folders": sizes, "size": total, "files": count}


def space_folder(user: User, space: str, rel_path: str) -> List[Path]:
    """Where a folder of a space is, on each disk (its root when the path is empty)."""
    folders = [f for f in candidates(user, space, rel_path) if f.is_dir()]
    if not folders and not rel_path.strip("/"):
        folders = [_space_root(user, space)]
    if not folders:
        raise HTTPException(404, "Folder not found")
    return folders


def recent_files(user: User, space: str, limit: int, skip_kinds=()) -> List[dict]:
    """The most recently changed files of a space, newest first."""
    found = ((mtime, rel, name, size, ctime) for _, name, size, mtime, rel, ctime in _files(user, space)
             if kind_of(name) not in skip_kinds)
    entries = []
    for mtime, rel, name, size, ctime in heapq.nlargest(limit, found, key=lambda f: f[0]):
        entries.append({
            "name": name,
            "path": rel,
            "is_dir": False,
            "size": size,
            "modified": mtime // 10**9,
            "added": ctime,
            "v": mtime,
            "kind": kind_of(name),
        })
    return entries


def trash_count(user: User) -> int:
    return len({slot.name for trash in _trash_roots(user) for slot in trash.iterdir() if not slot.name.startswith(".")})


def files_by_kind(user: User, space: str, kind: str) -> List[dict]:
    """Every file of one type in the whole space, newest first."""
    if kind not in KINDS and kind != "other":
        raise HTTPException(400, "Unknown type")
    found = []
    for folder, name, size, mtime, rel, ctime in _files(user, space):
        if kind_of(name) != kind:
            continue
        found.append({
            "name": name,
            "path": rel,
            "is_dir": False,
            "size": size,
            "modified": mtime // 10**9,
            "added": ctime,
            "_full": os.path.join(folder, name),
            "v": mtime,
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


def upload_plan(user: User, space: str, rel_path: str, name: str, size: int) -> dict:
    """Before uploading a file: is it already there (same name and size: skip it), was it
    half sent (resume from `offset`), or does another file have its name (use "name (2)")?"""
    name = _check_name(name)
    stem, suffix = os.path.splitext(name)
    rel = rel_path.strip("/")
    for n in range(1, 1000):
        candidate = name if n == 1 else f"{stem} ({n}){suffix}"
        existing = [p for p in candidates(user, space, os.path.join(rel, candidate)) if p.is_file()]
        if existing:
            if existing[0].stat().st_size == size:
                return {"name": candidate, "complete": True, "offset": size}
            continue  # a different file has this name: try the next one
        parts = [p for p in candidates(user, space, os.path.join(rel, f".{candidate}.part")) if p.is_file()]
        # Which stretches already arrived (pieces sent in any order), and how far in one go.
        ranges = [r for r in (pieces.load(parts[0]) if parts else []) if r[1] <= size]
        offset = ranges[0][1] if ranges and ranges[0][0] == 0 else 0
        return {"name": candidate, "complete": False, "offset": offset, "ranges": ranges}
    raise HTTPException(409, "Already exists")


def chunk_targets(user: User, space: str, rel_path: str, name: str):
    """Destination of a chunked upload and the hidden file it grows in meanwhile.
    All pieces of an upload go to the same disk: the one where it started."""
    name = _check_name(name)
    rel = rel_path.strip("/")
    if any(part.startswith(".") for part in rel.split("/") if part):
        raise HTTPException(400, "Invalid path")  # never into hidden folders (.nas_assistant, .trash…)
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


def keep_links(user: User, item_id: str, links: dict) -> None:
    """Remember what pointed at a trashed item (favorites, collections), to put it back with it.
    It lives and expires with the item, and never leaves the server: other users can be in it."""
    if not any(links.values()):
        return
    for slot in _trash_items(user, item_id):
        info = json.loads((slot / TRASH_INFO).read_text())
        (slot / TRASH_INFO).write_text(json.dumps({**info, "links": links}))


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
    """Put an item back where it was, on its own disk, recreating its folders if needed.
    Also says where it came from and what pointed at it, for the caller to link it again."""
    target = None
    links = {}
    for slot in _trash_items(user, item_id):
        info = _trash_info(slot)
        links = info.get("links") or links
        space = info["space"] if info["space"] in SPACES else "personal"
        disk = next(d for d in disk_roots() if d.resolve() in slot.resolve().parents)
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
    return {"space": space, "path": to_rel(user, space, target), "from": info["path"], "links": links}


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
