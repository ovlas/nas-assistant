"""Collections: albums of photos and dossiers of documents.

Like albums in Apple Photos, a collection only groups files: it never moves or
copies them, the same file can be in several collections, and removing it from
one leaves the file where it is. Items follow their files when they are renamed
or moved, leave when the file goes to the trash, and come back if it is restored.

A collection is personal (only its owner sees it) or shared with the family.
Shared collections only take files from the Family space, so nobody ever sees
someone else's private files through them.
"""

import secrets
import sqlite3
from contextlib import contextmanager
import time
from typing import List, Optional

from fastapi import HTTPException

from . import disks, storage
from .auth import User
from .kinds import kind_of

KINDS = ("album", "dossier")


def _connect() -> sqlite3.Connection:
    meta = disks.NAS_ROOT / ".nas_assistant"
    meta.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(meta / "index.db", timeout=30)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS collections (id TEXT PRIMARY KEY, owner TEXT, shared INTEGER, "
        "name TEXT, kind TEXT, created INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS collection_items (collection TEXT, space TEXT, path TEXT, added INTEGER, "
        "PRIMARY KEY (collection, space, path))"
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
    return storage._clean_rel(path)


def _get(conn: sqlite3.Connection, user: User, collection_id: str) -> dict:
    row = conn.execute("SELECT id, owner, shared, name, kind, created FROM collections WHERE id = ?",
                       (collection_id,)).fetchone()
    if not row or (not row[2] and row[1] != user.id):
        raise HTTPException(404, "Not found")
    return {"id": row[0], "owner": row[1], "shared": bool(row[2]), "name": row[3], "kind": row[4], "created": row[5]}


def _check_name(name: str) -> str:
    name = name.strip()[:80]
    if not name:
        raise HTTPException(422, "Required fields: name")
    return name


def _entry(user: User, space: str, path: str) -> Optional[dict]:
    """File details for an item, or None if the file is gone."""
    try:
        full = storage.resolve(user, space, path)
    except HTTPException:
        return None
    if not full.is_file():
        return None
    stat = full.stat()
    return {"space": space, "path": path, "name": full.name, "is_dir": False, "size": stat.st_size,
            "modified": int(stat.st_mtime), "added": int(stat.st_ctime), "v": stat.st_mtime_ns,
            "kind": kind_of(full.name), "_full": str(full)}


def listing(user: User) -> List[dict]:
    """The user's collections and the shared ones, with a count and up to 4 cover photos."""
    result = []
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, owner, shared, name, kind, created FROM collections WHERE owner = ? OR shared = 1 "
            "ORDER BY created DESC", (user.id,)).fetchall()
        for cid, owner, shared, name, kind, created in rows:
            items = conn.execute("SELECT space, path FROM collection_items WHERE collection = ? ORDER BY added DESC",
                                 (cid,)).fetchall()
            covers = []
            for space, path in items:
                if len(covers) == 4:
                    break
                if kind_of(path) in ("image", "video"):
                    entry = _entry(user, space, path)
                    if entry:
                        covers.append(entry)
            result.append({"id": cid, "name": name, "kind": kind, "shared": bool(shared), "mine": owner == user.id,
                           "created": created, "count": len(items), "covers": covers})
    return result


def create(user: User, name: str, kind: str, shared: bool) -> dict:
    if kind not in KINDS:
        raise HTTPException(400, "Unknown type")
    cid = secrets.token_hex(8)
    with _db() as conn:
        conn.execute("INSERT INTO collections VALUES (?, ?, ?, ?, ?, ?)",
                     (cid, user.id, int(shared), _check_name(name), kind, int(time.time())))
    return {"id": cid}


def rename(user: User, collection_id: str, name: str) -> None:
    with _db() as conn:
        _get(conn, user, collection_id)
        conn.execute("UPDATE collections SET name = ? WHERE id = ?", (_check_name(name), collection_id))


def delete(user: User, collection_id: str) -> None:
    """Delete a collection; its files stay where they are. Shared ones: their creator or an admin."""
    with _db() as conn:
        col = _get(conn, user, collection_id)
        if col["owner"] != user.id and not user.is_admin:
            raise HTTPException(403, "Only who created it can delete it")
        conn.execute("DELETE FROM collection_items WHERE collection = ?", (collection_id,))
        conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))


def items(user: User, collection_id: str) -> dict:
    with _db() as conn:
        col = _get(conn, user, collection_id)
        rows = conn.execute("SELECT space, path FROM collection_items WHERE collection = ? ORDER BY added DESC",
                            (collection_id,)).fetchall()
    entries = [e for e in (_entry(user, space, path) for space, path in rows) if e]
    return {**col, "mine": col["owner"] == user.id, "items": entries}


def add(user: User, collection_id: str, space: str, path: str) -> None:
    path = _clean(path)
    if not storage.resolve(user, space, path).is_file():
        raise HTTPException(404, "Not found")
    with _db() as conn:
        col = _get(conn, user, collection_id)
        if col["shared"] and space != "family":
            # Privacy: a shared collection must never show someone's private files.
            raise HTTPException(400, "Shared collections only take files from Family")
        conn.execute("INSERT OR IGNORE INTO collection_items VALUES (?, ?, ?, ?)",
                     (collection_id, space, path, int(time.time())))


def remove(user: User, collection_id: str, space: str, path: str) -> None:
    with _db() as conn:
        _get(conn, user, collection_id)
        conn.execute("DELETE FROM collection_items WHERE collection = ? AND space = ? AND path = ?",
                     (collection_id, space, _clean(path)))


# Collections whose items of `space` this user's change concerns: in Family every
# collection, in a personal space only the user's own (nobody else can hold them).
_SCOPE = ("space = ? AND (space = 'family' OR collection IN (SELECT id FROM collections WHERE owner = ?))")


def moved(user: User, space: str, old: str, to_space: str, new: str) -> None:
    """Keep items (and everything inside a moved folder) after a rename or move."""
    old, new = _clean(old), _clean(new)
    with _db() as conn:
        rows = conn.execute(
            f"SELECT collection, path FROM collection_items WHERE {_SCOPE} AND (path = ? OR path LIKE ?)",
            (space, user.id, old, old + "/%")).fetchall()
        for cid, path in rows:
            conn.execute("DELETE FROM collection_items WHERE collection = ? AND space = ? AND path = ?",
                         (cid, space, path))
            shared, owner = conn.execute("SELECT shared, owner FROM collections WHERE id = ?", (cid,)).fetchone()
            # Out of Family: shared collections (and other people's) can't follow it into a private space.
            if to_space == "family" or (not shared and owner == user.id):
                conn.execute("INSERT OR IGNORE INTO collection_items VALUES (?, ?, ?, ?)",
                             (cid, to_space, new + path[len(old):], int(time.time())))


def removed(user: User, space: str, path: str) -> List[list]:
    """Take a trashed item out of its collections; returns what was there, for restored()."""
    path = _clean(path)
    where = f"{_SCOPE} AND (path = ? OR path LIKE ?)"
    args = (space, user.id, path, path + "/%")
    with _db() as conn:
        rows = conn.execute(f"SELECT collection, path, added FROM collection_items WHERE {where}", args).fetchall()
        conn.execute(f"DELETE FROM collection_items WHERE {where}", args)
    return [list(row) for row in rows]


def restored(user: User, links: List[list], space: str, old: str, new: str) -> None:
    """Back in the collections it was in, under the name it came back with."""
    old, new = _clean(old), _clean(new)
    with _db() as conn:
        for cid, path, added in links:
            found = conn.execute("SELECT shared, owner FROM collections WHERE id = ?", (cid,)).fetchone()
            if not found:  # the collection was deleted in the meantime
                continue
            shared, owner = found
            if space == "family" or (not shared and owner == user.id):
                conn.execute("INSERT OR IGNORE INTO collection_items VALUES (?, ?, ?, ?)",
                             (cid, space, new + path[len(old):], added))
