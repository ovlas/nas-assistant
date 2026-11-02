"""Other files on the disks: what is on the NAS and extra-storage disks outside
NAS Assistant's own folders (e.g. a disk that already held photos, music or old
documents before it was given to the NAS).

Administrators only, read only: browse, preview, download, and copy into My space
or Family. Nothing here renames, moves or deletes anything on the disk, and the
folders of NAS Assistant itself and of the operating systems are left out.
"""

import os
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, List

from fastapi import HTTPException

from . import disks, storage
from .auth import User
from .kinds import kind_of

PREFIX = "disk:"
# Folders of Windows, macOS and NAS Assistant that nobody wants to browse.
SYSTEM_NAMES = {"System Volume Information", "lost+found", "Recovery", "Config.Msi", "found.000"}
jobs: Dict[str, dict] = {}
_lock = threading.Lock()


def mounts() -> Dict[str, Path]:
    """Disks that can be browsed now: "nas" and "storage"."""
    result = {}
    if disks.state() == "mounted":
        result["nas"] = disks.NAS_ROOT
    if storage.EXTRA_STATE == "mounted":
        result["storage"] = storage.EXTRA_MOUNT
    return result


def _hidden_at_root(mount: Path) -> set:
    names = {storage.DATA_FOLDER, ".nas_assistant", ".trash"}
    if storage.data_root(mount, mount / storage.DATA_FOLDER) == mount:
        names |= {"users", "family"}  # a former NAS disk keeps its files at the root
    return names


def _visible(name: str) -> bool:
    return not (name.startswith((".", "$", "~$")) or name in SYSTEM_NAMES)


def _mount(space: str) -> Path:
    mount = mounts().get(space[len(PREFIX):]) if space.startswith(PREFIX) else None
    if not mount:
        raise HTTPException(404, "Disk not connected")
    return mount


def resolve(space: str, rel: str) -> Path:
    """A path on the disk, refusing hidden folders and anything outside the disk."""
    mount = _mount(space)
    parts = [p for p in rel.strip("/").split("/") if p]
    if any(p in ("..", ".") or not _visible(p) for p in parts) or (parts and parts[0] in _hidden_at_root(mount)):
        raise HTTPException(404, "File not found")
    target = mount.joinpath(*parts)
    real, root = os.path.realpath(target), os.path.realpath(mount)
    if real != root and not real.startswith(root + os.sep):
        raise HTTPException(404, "File not found")  # a link pointing outside the disk
    if not os.path.exists(target):
        raise HTTPException(404, "File not found")
    return target


def list_dir(space: str, rel: str) -> List[dict]:
    folder = resolve(space, rel)
    if not folder.is_dir():
        raise HTTPException(404, "Folder not found")
    hidden = _hidden_at_root(_mount(space)) if not rel.strip("/") else set()
    entries = []
    try:
        items = list(os.scandir(folder))
    except OSError:
        raise HTTPException(403, "Can't open the folder")
    for entry in items:
        if not _visible(entry.name) or entry.name in hidden:
            continue
        try:
            stat = entry.stat()
            is_dir = entry.is_dir()
        except OSError:
            continue
        entries.append({
            "name": entry.name,
            "is_dir": is_dir,
            "size": 0 if is_dir else stat.st_size,
            "modified": int(stat.st_mtime),
            "v": stat.st_mtime_ns,
            "kind": None if is_dir else kind_of(entry.name),
        })
    return sorted(entries, key=lambda e: (not e["is_dir"], e["name"].lower()))


# --- Copy into My space or Family ----------------------------------------------

def _size(src: Path) -> int:
    if src.is_file():
        return src.stat().st_size
    total = 0
    for top, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if _visible(d)]
        for name in files:
            if _visible(name):
                try:
                    total += os.path.getsize(os.path.join(top, name))
                except OSError:
                    pass
    return total


def _free_name(folder: Path, name: str) -> Path:
    """"name", or "name (2)", "name (3)"… if that is taken."""
    target = folder / name
    stem, suffix = (Path(name).stem, Path(name).suffix) if not (folder / name).is_dir() else (name, "")
    n = 2
    while target.exists():
        target = folder / f"{stem} ({n}){suffix}"
        n += 1
    return target


def start_copy(user: User, space: str, rel: str, to_space: str, to_path: str) -> dict:
    """Copy a file or folder of the disk into a space, in the background."""
    src = resolve(space, rel)
    if not rel.strip("/"):
        raise HTTPException(400, "Choose a file or a folder")
    dest_dir = storage.resolve(user, to_space, to_path)
    if not dest_dir.is_dir():
        raise HTTPException(404, "Folder not found")
    total = _size(src)
    if total > shutil.disk_usage(dest_dir).free - 1024 ** 3:  # keep 1 GB free
        raise HTTPException(507, "Not enough free space")
    job = {"id": secrets.token_hex(6), "user_id": user.id, "name": src.name, "space": to_space,
           "path": to_path, "total": total, "done": 0, "state": "copying", "error": "", "at": time.time()}
    with _lock:
        jobs[job["id"]] = job
    threading.Thread(target=_copy, args=(job, src, dest_dir), daemon=True).start()
    return job


def _copy_file(job: dict, src: Path, dst: Path) -> None:
    partial = dst.with_name(f".{dst.name}.part")
    with open(src, "rb") as fin, open(partial, "wb") as fout:
        while chunk := fin.read(4 * 1024 * 1024):
            fout.write(chunk)
            job["done"] += len(chunk)
    shutil.copystat(src, partial)
    os.replace(partial, dst)


def _copy(job: dict, src: Path, dest_dir: Path) -> None:
    try:
        target = _free_name(dest_dir, src.name)
        if src.is_file():
            _copy_file(job, src, target)  # resolve() already refused a link leading outside
        else:
            for top, dirs, files in os.walk(src):
                dirs[:] = sorted(d for d in dirs if _visible(d) and not os.path.islink(os.path.join(top, d)))
                out = target / os.path.relpath(top, src)
                out.mkdir(parents=True, exist_ok=True)
                for name in sorted(files):
                    # Links are skipped: they could point outside the disk.
                    if _visible(name) and not os.path.islink(os.path.join(top, name)):
                        try:
                            _copy_file(job, Path(top) / name, out / name)
                        except PermissionError:
                            continue  # an unreadable file: copy the rest
        job["state"] = "done"
    except OSError as err:
        job["state"], job["error"] = "error", err.strerror or str(err)


def user_jobs(user: User) -> List[dict]:
    """This user's copies: running ones, and those finished in the last minutes."""
    now = time.time()
    with _lock:
        for job_id in [i for i, j in jobs.items() if j["state"] != "copying" and now - j["at"] > 3600]:
            del jobs[job_id]
        return [{k: v for k, v in j.items() if k != "user_id"} for j in jobs.values() if j["user_id"] == user.id]
