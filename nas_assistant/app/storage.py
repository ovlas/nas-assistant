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

from .auth import User

NAS_ROOT = Path(os.environ.get("NAS_ROOT", "/nas"))
CHUNK = 1024 * 1024
SPACES = ("personal", "family")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def disk_state() -> str:
    return os.environ.get("NAS_DISK_STATE", "mounted")


def _require_disk() -> None:
    if disk_state() != "mounted":
        # Never fall back to the main disk.
        raise HTTPException(503, "Disco NAS non disponibile")


def _space_root(user: User, space: str) -> Path:
    if not _SAFE_ID.match(user.id):
        raise HTTPException(400, "ID utente non valido")
    if space == "personal":
        root = NAS_ROOT / "users" / user.id
    elif space == "family":
        root = NAS_ROOT / "family"
    else:
        raise HTTPException(400, "Spazio sconosciuto")
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve(user: User, space: str, rel_path: str) -> Path:
    """Map a user-supplied path to a real path, refusing anything outside the space."""
    _require_disk()
    root = _space_root(user, space).resolve()
    target = (root / rel_path.lstrip("/")).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(400, "Percorso non valido")
    return target


def _check_name(name: str) -> str:
    name = name.strip()
    if not name or name in (".", "..") or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "Nome non valido")
    return name


def list_dir(user: User, space: str, rel_path: str) -> List[dict]:
    folder = resolve(user, space, rel_path)
    if not folder.is_dir():
        raise HTTPException(404, "Cartella non trovata")
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
        })
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries


def make_dir(user: User, space: str, rel_path: str, name: str) -> None:
    target = resolve(user, space, rel_path) / _check_name(name)
    if target.exists():
        raise HTTPException(409, "Esiste già")
    target.mkdir()


def save_file(user: User, space: str, rel_path: str, name: str, data: BinaryIO) -> dict:
    folder = resolve(user, space, rel_path)
    if not folder.is_dir():
        raise HTTPException(404, "Cartella non trovata")
    target = folder / _check_name(name)
    # Write to a hidden temp file first so a dropped upload never leaves a broken file.
    partial = folder / f".{target.name}.part"
    with open(partial, "wb") as out:
        shutil.copyfileobj(data, out, CHUNK)
    os.replace(partial, target)
    return {"name": target.name, "size": target.stat().st_size}


def move_to_trash(user: User, space: str, rel_path: str) -> None:
    target = resolve(user, space, rel_path)
    if target == _space_root(user, space).resolve():
        raise HTTPException(400, "Impossibile eliminare la radice")
    if not target.exists():
        raise HTTPException(404, "Non trovato")
    trash = NAS_ROOT / ".trash" / user.id
    trash.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target), str(trash / f"{int(time.time())}_{target.name}"))


def usage() -> dict:
    _require_disk()
    total, used, free = shutil.disk_usage(NAS_ROOT)
    return {"total": total, "used": used, "free": free}
