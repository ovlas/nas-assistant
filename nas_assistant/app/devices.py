"""Device keys: let a phone send files to the NAS on its own, e.g. an iOS Shortcut
running in the background, without a Home Assistant login on it.

A key belongs to one user and can only upload into that user's space: it can't
list, download or delete anything. Keys are stored hashed in /data and can be
revoked from the web UI at any time.
"""

import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException

from .auth import User

DEVICES_FILE = Path(os.environ.get("NAS_DEVICES_FILE", "/data/devices.json"))
PREFIX = "nas_"
_lock = threading.Lock()


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _load() -> List[dict]:
    try:
        return json.loads(DEVICES_FILE.read_text())
    except (OSError, ValueError):
        return []


def _save(devices: List[dict]) -> None:
    partial = DEVICES_FILE.with_suffix(".part")
    partial.write_text(json.dumps(devices))
    os.replace(partial, DEVICES_FILE)


def create(user: User, name: str) -> str:
    """Add a device for this user; returns its key, shown only once."""
    name = name.strip()[:60]
    if not name:
        raise HTTPException(422, "Required fields: name")
    key = PREFIX + secrets.token_urlsafe(32)
    with _lock:
        devices = _load()
        devices.append({
            "id": secrets.token_hex(8),
            "user_id": user.id,
            "user_name": user.name,
            "display_name": user.display_name,
            "name": name,
            "hash": _hash(key),
            "created": int(time.time()),
            "last_used": None,
        })
        _save(devices)
    return key


def listing(user: User) -> List[dict]:
    return [{k: d[k] for k in ("id", "name", "created", "last_used")}
            for d in _load() if d["user_id"] == user.id]


def revoke(user: User, device_id: str) -> None:
    with _lock:
        devices = _load()
        kept = [d for d in devices if not (d["id"] == device_id and d["user_id"] == user.id)]
        if len(kept) == len(devices):
            raise HTTPException(404, "Not found")
        _save(kept)


def owner(key: str) -> Optional[User]:
    """The user a device key belongs to, or None if the key is unknown or revoked."""
    if not key.startswith(PREFIX):
        return None
    digest = _hash(key)
    with _lock:
        devices = _load()
        for device in devices:
            if secrets.compare_digest(device["hash"], digest):
                # Note when it was last used, at most once a minute.
                if not device["last_used"] or time.time() - device["last_used"] > 60:
                    device["last_used"] = int(time.time())
                    _save(devices)
                return User(id=device["user_id"], name=device["user_name"],
                            display_name=device["display_name"], is_admin=False)
    return None
