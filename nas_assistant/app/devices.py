"""Device keys: let a phone send files to the NAS on its own (the mobile app, or an
iOS Shortcut running in the background) without a Home Assistant login on it.

Phones are paired with a one-time QR code: it expires after a few minutes, works
once, and the key it is exchanged for never appears on screen.

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
PAIRING_SECONDS = 10 * 60
MAX_FAILED_PAIRINGS = 10  # per address and minute
_lock = threading.Lock()
_pairings = {}  # code -> (user, expires)
_failures = {}  # client address -> (window start, count)


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


def create(user: User, name: str, platform: str = "") -> str:
    """Add a device for this user; returns its key."""
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
            "platform": platform[:20],
            "hash": _hash(key),
            "created": int(time.time()),
            "last_used": None,
        })
        _save(devices)
    return key


def listing(user: User) -> List[dict]:
    return [{"id": d["id"], "name": d["name"], "platform": d.get("platform", ""),
             "created": d["created"], "last_used": d["last_used"]}
            for d in _load() if d["user_id"] == user.id]


def start_pairing(user: User) -> dict:
    """A one-time code for the QR shown on the web page."""
    now = time.time()
    for code in [c for c, (_, expires) in _pairings.items() if expires < now]:
        del _pairings[code]
    code = secrets.token_urlsafe(18)
    _pairings[code] = (user, now + PAIRING_SECONDS)
    return {"code": code, "expires": int(now + PAIRING_SECONDS)}


def pair(code: str, name: str, platform: str, client: str) -> dict:
    """Exchange a QR code for a device key. Each code works once."""
    now = time.time()
    start, count = _failures.get(client, (now, 0))
    if now - start > 60:
        start, count = now, 0
    if count >= MAX_FAILED_PAIRINGS:
        raise HTTPException(429, "Too many attempts, try again in a minute")
    entry = _pairings.pop(code, None)
    if not entry or entry[1] < now:
        _failures[client] = (start, count + 1)
        raise HTTPException(403, "This QR code is no longer valid: show a new one on the NAS page")
    user = entry[0]
    key = create(user, name or "Phone", platform)
    device = next(d for d in _load() if d["hash"] == _hash(key))
    return {"key": key, "device_id": device["id"], "user": {"display_name": user.display_name}}


def is_paired(user: User, since: float) -> bool:
    """True once a device of this user was added after `since` (the web page waits for it)."""
    return any(d["user_id"] == user.id and d["created"] >= since for d in _load())


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
                            display_name=device["display_name"], is_admin=False, device=device["name"])
    return None
