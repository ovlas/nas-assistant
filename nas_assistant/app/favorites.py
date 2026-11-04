"""Favorites: files, folders, photos and videos each user marks with a heart.

Each user has their own favorites, also in the Family space. They live in the
index on the NAS disk (.nas_assistant/index.db), follow items when they are
renamed or moved, and come back when an item is restored from the trash.
"""

import os
import sqlite3
from contextlib import contextmanager
import time
from typing import List, Set

from fastapi import HTTPException

from . import disks, storage
from .auth import User
from .kinds import kind_of


def _connect() -> sqlite3.Connection:
    meta = disks.NAS_ROOT / ".nas_assistant"
    meta.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(meta / "index.db", timeout=30)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS favorites (user TEXT, space TEXT, path TEXT, added INTEGER, "
        "PRIMARY KEY (user, space, path))"
    )
    return conn


@contextmanager
def _db():
    """Commit and always close: an open handle on the disk would stop it from being ejected."""
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _clean(path: str) -> str:
    return os.path.normpath(path.strip("/")) if path.strip("/") else ""


# Rows that an item of `space` concerns: in Family every user's favorites,
# in a personal space only its owner's.
_SCOPE = "space = ? AND (space = 'family' OR user = ?)"


def set_favorite(user: User, space: str, path: str, on: bool) -> None:
    target = storage.resolve(user, space, path)
    if not target.exists():
        raise HTTPException(404, "Not found")
    path = _clean(path)
    with _db() as conn:
        if on:
            conn.execute("INSERT OR IGNORE INTO favorites VALUES (?, ?, ?, ?)",
                         (user.id, space, path, int(time.time())))
        else:
            conn.execute("DELETE FROM favorites WHERE user = ? AND space = ? AND path = ?", (user.id, space, path))


def paths(user: User, space: str) -> Set[str]:
    with _db() as conn:
        rows = conn.execute("SELECT path FROM favorites WHERE user = ? AND space = ?", (user.id, space)).fetchall()
    return {row[0] for row in rows}


def listing(user: User, space: str) -> List[dict]:
    """The user's favorites in a space, newest first; forgets items that are gone."""
    entries, gone = [], []
    with _db() as conn:
        rows = conn.execute(
            "SELECT path FROM favorites WHERE user = ? AND space = ? ORDER BY added DESC", (user.id, space)
        ).fetchall()
        for (path,) in rows:
            try:
                full = storage.resolve(user, space, path)
            except HTTPException:  # e.g. on the extra disk while it is unplugged
                continue
            if not full.exists():
                gone.append(path)
                continue
            stat = full.stat()
            is_dir = full.is_dir()
            entries.append({
                "name": full.name,
                "path": path,
                "is_dir": is_dir,
                "size": 0 if is_dir else stat.st_size,
                "modified": int(stat.st_mtime),
                "added": int(stat.st_ctime),
                "_full": str(full),
                "v": stat.st_mtime_ns,
                "kind": None if is_dir else kind_of(full.name),
                "fav": True,
            })
        conn.executemany("DELETE FROM favorites WHERE user = ? AND space = ? AND path = ?",
                         [(user.id, space, p) for p in gone])
    return entries


def moved(user: User, space: str, old: str, to_space: str, new: str) -> None:
    """Keep favorites on an item (and everything inside a folder) after a rename or move."""
    old, new = _clean(old), _clean(new)
    with _db() as conn:
        rows = conn.execute(
            f"SELECT user, path FROM favorites WHERE {_SCOPE} AND (path = ? OR path LIKE ?)",
            (space, user.id, old, old + "/%"),
        ).fetchall()
        for owner, path in rows:
            conn.execute("DELETE FROM favorites WHERE user = ? AND space = ? AND path = ?", (owner, space, path))
            # Moving out of Family keeps only the mover's favorites: the others can't see it anymore.
            if to_space == space or owner == user.id:
                conn.execute("INSERT OR IGNORE INTO favorites VALUES (?, ?, ?, ?)",
                             (owner, to_space, new + path[len(old):], int(time.time())))


def removed(user: User, space: str, path: str) -> List[list]:
    """Drop the favorites of a trashed item; returns what was there, for restored()."""
    path = _clean(path)
    where = f"{_SCOPE} AND (path = ? OR path LIKE ?)"
    args = (space, user.id, path, path + "/%")
    with _db() as conn:
        rows = conn.execute(f"SELECT user, path, added FROM favorites WHERE {where}", args).fetchall()
        conn.execute(f"DELETE FROM favorites WHERE {where}", args)
    return [list(row) for row in rows]


def restored(user: User, links: List[list], space: str, old: str, new: str) -> None:
    """Favorites again, under the name the item came back with."""
    old, new = _clean(old), _clean(new)
    with _db() as conn:
        for owner, path, added in links:
            if space == "family" or owner == user.id:
                conn.execute("INSERT OR IGNORE INTO favorites VALUES (?, ?, ?, ?)",
                             (owner, space, new + path[len(old):], added))
