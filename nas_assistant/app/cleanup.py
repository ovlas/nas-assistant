"""Cleanup: exact duplicates and similar photos, to free space.

Duplicates are files with the very same bytes, whatever their names or folders. Reading
a whole library (maybe a terabyte, on USB 2) to compare would take hours, so: files of
different sizes can't be equal; among same-size files, a quick fingerprint (size, the first
and the last 64 KB) sorts out almost all; only files that still match are read entirely
(SHA-256). Fingerprints are kept, so the next scan only reads what changed.

Similar photos (bursts, the same shot resized or saved again) get a 64-bit "difference
hash" from their thumbnail; hashes a few bits apart are the same picture. To avoid
comparing every pair, photos are bucketed by four 16-bit slices of the hash: two similar
hashes share at least one slice exactly.

Nothing is deleted here: the page moves what the user picks to Recently deleted.
"""

import hashlib
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from . import media, storage
from .auth import User
from .kinds import media_kind

QUICK_BYTES = 64 * 1024
SIMILAR_BITS = 6  # at most this many of the 64 bits differ
MAX_GROUPS = 500
_scans: Dict[Tuple[str, str], dict] = {}  # (user, space) -> state and results
_lock = threading.Lock()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(media._meta_dir() / "index.db", timeout=30)
    conn.execute("CREATE TABLE IF NOT EXISTS fingerprints (path TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER, "
                 "quick TEXT, full TEXT, dhash INTEGER)")
    return conn


def _quick(path: str, size: int) -> str:
    """For files up to 128 KB the whole content; else the size, the first and the last 64 KB."""
    h = hashlib.sha256(str(size).encode())
    with open(path, "rb") as f:
        if size <= 2 * QUICK_BYTES:
            h.update(f.read())
        else:
            h.update(f.read(QUICK_BYTES))
            f.seek(-QUICK_BYTES, os.SEEK_END)
            h.update(f.read(QUICK_BYTES))
    return h.hexdigest()


def _full(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _dhash(path: str) -> Optional[int]:
    """64-bit difference hash of a photo, from its small thumbnail (made if missing)."""
    src = Path(path)
    try:
        thumb = media.thumb_path(src, "s")
        if not thumb.exists():
            media.make_thumbnail(src, "s", thumb)
        with Image.open(thumb) as img:
            small = img.convert("L").resize((9, 8), Image.LANCZOS)
            pixels = list(small.getdata())
    except Exception:
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits - (1 << 63)  # SQLite integers are signed


def status(user: User, space: str) -> dict:
    scan = _scans.get((user.id, space))
    if not scan:
        return {"state": "idle"}
    return {k: v for k, v in scan.items() if k != "thread"}


def start(user: User, space: str) -> dict:
    key = (user.id, space)
    with _lock:
        scan = _scans.get(key)
        if scan and scan["state"] == "scanning":
            return status(user, space)
        _scans[key] = {"state": "scanning", "phase": "listing", "done": 0, "total": 0, "started": time.time()}
        threading.Thread(target=_scan, args=(user, space), daemon=True).start()
    return status(user, space)


def _scan(user: User, space: str) -> None:
    scan = _scans[(user.id, space)]
    try:
        files = [(os.path.join(folder, name), rel, size, mtime)
                 for folder, name, size, mtime, rel, _ in storage._files(user, space) if size > 0]
        conn = _db()
        try:
            known = {row[0]: row[1:] for row in conn.execute(
                "SELECT path, mtime_ns, size, quick, full, dhash FROM fingerprints")}
            duplicates = _duplicates(files, known, conn, scan)
            similar = _similar(files, known, conn, scan, duplicates)
            conn.commit()
        finally:
            conn.close()
        scan.update({"state": "ready", "phase": "", "duplicates": duplicates, "similar": similar,
                     "finished": time.time(), "files": len(files)})
    except Exception as err:  # e.g. the disk went away
        scan.update({"state": "error", "error": str(err)})


def _remember(conn, known, path, mtime, size, **values) -> None:
    old = known.get(path)
    row = dict(zip(("mtime", "size", "quick", "full", "dhash"), old)) if old and old[0] == mtime and old[1] == size \
        else {"mtime": mtime, "size": size, "quick": None, "full": None, "dhash": None}
    row.update(values)
    known[path] = (row["mtime"], row["size"], row["quick"], row["full"], row["dhash"])
    conn.execute("INSERT OR REPLACE INTO fingerprints VALUES (?, ?, ?, ?, ?, ?)",
                 (path, row["mtime"], row["size"], row["quick"], row["full"], row["dhash"]))


def _cached(known, path, mtime, size, field: int):
    row = known.get(path)
    return row[field] if row and row[0] == mtime and row[1] == size else None


def _entry(rel: str, path: str, size: int, mtime: int) -> dict:
    return {"path": rel, "name": os.path.basename(path), "size": size, "modified": mtime // 10**9,
            "v": mtime, "kind": media_kind(path)}


def _duplicates(files, known, conn, scan) -> List[dict]:
    by_size: Dict[int, list] = {}
    for item in files:
        by_size.setdefault(item[2], []).append(item)
    candidates = [group for group in by_size.values() if len(group) > 1]
    scan.update({"phase": "duplicates", "done": 0, "total": sum(len(g) for g in candidates)})
    groups = []
    for group in candidates:
        by_quick: Dict[str, list] = {}
        for path, rel, size, mtime in group:
            quick = _cached(known, path, mtime, size, 2)
            if not quick:
                try:
                    quick = _quick(path, size)
                except OSError:
                    continue
                _remember(conn, known, path, mtime, size, quick=quick)
            by_quick.setdefault(quick, []).append((path, rel, size, mtime))
            scan["done"] += 1
        for same in (g for g in by_quick.values() if len(g) > 1):
            by_full: Dict[str, list] = {}
            for path, rel, size, mtime in same:
                full = _cached(known, path, mtime, size, 3) if size > 2 * QUICK_BYTES else "small"
                if not full:
                    try:
                        full = _full(path)
                    except OSError:
                        continue
                    _remember(conn, known, path, mtime, size, full=full)
                by_full.setdefault(full, []).append((path, rel, size, mtime))
            for equal in (g for g in by_full.values() if len(g) > 1):
                equal.sort(key=lambda f: f[3])  # the oldest first: it is the one kept by default
                groups.append({"size": equal[0][2], "waste": equal[0][2] * (len(equal) - 1),
                               "files": [_entry(rel, path, size, mtime) for path, rel, size, mtime in equal]})
        conn.commit()
    groups.sort(key=lambda g: -g["waste"])
    return groups[:MAX_GROUPS]


def _similar(files, known, conn, scan, duplicates) -> List[dict]:
    exact = {f["path"] for g in duplicates for f in g["files"][1:]}  # extra copies are listed already
    photos = [f for f in files if media_kind(f[0]) == "image" and f[1] not in exact]
    scan.update({"phase": "similar", "done": 0, "total": len(photos)})
    hashes: List[Tuple[int, tuple]] = []
    for path, rel, size, mtime in photos:
        value = _cached(known, path, mtime, size, 4)
        if value is None:
            value = _dhash(path)
            if value is None:
                scan["done"] += 1
                continue
            _remember(conn, known, path, mtime, size, dhash=value)
            if scan["done"] % 200 == 0:
                conn.commit()
        hashes.append((value + (1 << 63), (path, rel, size, mtime)))
        scan["done"] += 1
    # Bucket by four 16-bit slices: hashes at most 6 bits apart share at least one slice.
    parent = list(range(len(hashes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for band in range(4):
        buckets: Dict[int, List[int]] = {}
        for i, (value, _) in enumerate(hashes):
            buckets.setdefault((value >> (16 * band)) & 0xFFFF, []).append(i)
        for members in buckets.values():
            if len(members) > 200:  # a flat slice (plain colour): too common to mean anything
                continue
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    i, j = members[a], members[b]
                    if bin(hashes[i][0] ^ hashes[j][0]).count("1") <= SIMILAR_BITS:
                        parent[find(i)] = find(j)
    clusters: Dict[int, list] = {}
    for i in range(len(hashes)):
        clusters.setdefault(find(i), []).append(hashes[i][1])
    groups = []
    for members in (m for m in clusters.values() if len(m) > 1):
        members.sort(key=lambda f: -f[2])  # the biggest (usually the best) first
        groups.append({"waste": sum(f[2] for f in members[1:]),
                       "files": [_entry(rel, path, size, mtime) for path, rel, size, mtime in members]})
    groups.sort(key=lambda g: -g["waste"])
    return groups[:MAX_GROUPS]
