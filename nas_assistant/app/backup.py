"""Backup of the NAS disk to a second disk, like a mature NAS.

Every night (and on demand) the NAS disk is copied to the backup disk,
incrementally: only files whose size or date changed are copied. Nothing is lost between two
backups: when a file is changed or deleted, its previous copy moves to
versions/<date>/ and stays there for `backup_keep_days` days.

Everything is written inside one folder of the backup disk,
"NAS Assistant Backup"; nothing else on that disk is ever touched, and the
disk is never formatted.
"""

import asyncio
import json
import logging
import os
import shutil
import stat
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from . import disks

log = logging.getLogger("uvicorn.error")

ROOT = Path(os.environ.get("NAS_BACKUP_ROOT", "/backup"))
FOLDER = ROOT / "NAS Assistant Backup"
CURRENT = FOLDER / "current"
VERSIONS = FOLDER / "versions"
STATUS_FILE = Path(os.environ.get("NAS_BACKUP_STATUS", "/data/backup.json"))
STATE = os.environ.get("NAS_BACKUP_STATE", "none")  # none, mounted, missing, same
SAME_DISK = os.environ.get("NAS_BACKUP_SAME_DISK") == "1"
AT = os.environ.get("NAS_BACKUP_TIME", "03:00")
KEEP_DAYS = int(os.environ.get("NAS_BACKUP_KEEP_DAYS", "30"))
STAMP = "%Y-%m-%d_%H%M"
# Rebuilt by the add-on, deleted on purpose, or written by the operating system.
EXCLUDED_PATHS = (
    ".nas_assistant/thumbs", ".trash", "lost+found", "System Volume Information", "$RECYCLE.BIN",
)
CHUNK = 4 * 1024 * 1024

_lock = threading.Lock()
_progress = {"running": False, "percent": 0, "started": None}


def _load() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    STATUS_FILE.write_text(json.dumps(data))


def next_run(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now()
    hour, minute = map(int, AT.split(":"))
    run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return run if run > now else run + timedelta(days=1)


def _prune_versions() -> None:
    limit = datetime.now() - timedelta(days=KEEP_DAYS)
    for version in VERSIONS.iterdir():
        try:
            taken = datetime.strptime(version.name, STAMP)
        except ValueError:
            continue  # not ours
        if taken < limit:
            shutil.rmtree(version, ignore_errors=True)


def _excluded(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if name.startswith(".") and name.endswith(".part"):
        return True  # uploads in progress
    return any(rel == e or rel.startswith(e + "/") for e in EXCLUDED_PATHS)


def _scan(root: Path) -> dict:
    """{relative path: (size, mtime)} of every file under root, skipping exclusions."""
    files = {}
    for folder, dirs, names in os.walk(root):
        base = os.path.relpath(folder, root)
        base = "" if base == "." else base + "/"
        dirs[:] = [d for d in dirs if not _excluded(base + d)]
        for name in names:
            rel = base + name
            if _excluded(rel):
                continue
            try:
                st = os.lstat(os.path.join(folder, name))
            except OSError:
                continue  # vanished meanwhile
            if stat.S_ISREG(st.st_mode):  # regular files only, no links or devices
                files[rel] = (st.st_size, st.st_mtime)
    return files


def _keep_old(rel: str, version_dir: Path) -> None:
    """Move the backup copy of a file into this run's versions folder."""
    old = CURRENT / rel
    target = version_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(old, target)


def _copy(rel: str, done: list, total: int) -> None:
    src = disks.NAS_ROOT / rel
    dst = CURRENT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    partial = dst.with_name(f".{dst.name}.nasbackup")
    with open(src, "rb") as fin, open(partial, "wb") as fout:
        while True:
            chunk = fin.read(CHUNK)
            if not chunk:
                break
            fout.write(chunk)
            done[0] += len(chunk)
            _progress["percent"] = min(99, int(done[0] * 100 / total)) if total else 0
    shutil.copystat(src, partial)
    os.replace(partial, dst)


def run() -> dict:
    """Run one backup now. Blocking: call it from a worker thread.

    Only what changed (size or modification time) is copied. The previous
    copy of a changed or deleted file is moved to versions/<date>/."""
    if STATE != "mounted":
        raise HTTPException(503, "Backup disk not available")
    if disks.state() != "mounted":
        raise HTTPException(503, "NAS disk not available")
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "A backup is already running")
    started = int(time.time())
    result = {"start": started, "ok": False, "files": 0, "bytes": 0, "kept": 0}
    errors = []
    try:
        _progress.update(running=True, percent=0, started=started)
        CURRENT.mkdir(parents=True, exist_ok=True)
        VERSIONS.mkdir(parents=True, exist_ok=True)
        version_dir = VERSIONS / datetime.now().strftime(STAMP)
        source = _scan(disks.NAS_ROOT)
        backed = _scan(CURRENT)
        # FAT/exFAT keep times to 2 seconds: smaller differences are not changes.
        changed = [rel for rel, (size, mtime) in source.items()
                   if rel not in backed or backed[rel][0] != size or abs(backed[rel][1] - mtime) > 2]
        gone = [rel for rel in backed if rel not in source]
        total = sum(source[rel][0] for rel in changed)
        done = [0]
        for rel in gone:
            try:
                _keep_old(rel, version_dir)
                result["kept"] += 1
            except OSError as err:
                errors.append(f"{rel}: {err}")
        for rel in changed:
            try:
                if rel in backed:
                    _keep_old(rel, version_dir)
                    result["kept"] += 1
                _copy(rel, done, total)
                result["files"] += 1
                result["bytes"] += source[rel][0]
            except OSError as err:
                errors.append(f"{rel}: {err}")
        # Folders that no longer exist on the NAS disk (now empty in the backup).
        for folder, dirs, names in os.walk(CURRENT, topdown=False):
            if folder != str(CURRENT) and not os.listdir(folder):
                rel = os.path.relpath(folder, CURRENT)
                if not (disks.NAS_ROOT / rel).is_dir():
                    os.rmdir(folder)
        result["ok"] = not errors
        result["message"] = f"{len(errors)} errors, first: {errors[0]}" if errors else ""
        _prune_versions()
    except OSError as err:
        result["message"] = str(err)
    finally:
        result["end"] = int(time.time())
        _progress.update(running=False, percent=0, started=None)
        data = _load()
        data["last"] = result
        if result["ok"]:
            data["last_ok"] = result["end"]
        _save(data)
        _lock.release()
        log.info("Backup %s: %s", "done" if result["ok"] else "failed",
                 {k: v for k, v in result.items() if k != "message"} | {"message": result.get("message", "")[:200]})
    return result


def status() -> dict:
    data = _load()
    info = {
        "state": STATE,
        "same_disk": SAME_DISK,
        "running": _progress["running"],
        "percent": _progress["percent"],
        "last": data.get("last"),
        "last_ok": data.get("last_ok"),
        "next": int(next_run().timestamp()) if STATE == "mounted" else None,
        "time": AT,
        "keep_days": KEEP_DAYS,
        # For the "open the add-on configuration" link: the hostname is the slug with dashes.
        "addon": os.environ.get("HOSTNAME", "").replace("-", "_"),
    }
    if STATE == "mounted":
        total, used, free = shutil.disk_usage(ROOT)
        info["usage"] = {"total": total, "used": used, "free": free}
        info["versions"] = len([v for v in VERSIONS.iterdir() if v.is_dir()]) if VERSIONS.exists() else 0
    return info


async def start() -> bool:
    """Start a backup in the background; False if one is already running."""
    if _lock.locked():
        return False
    asyncio.get_running_loop().create_task(_run_logged())
    return True


async def _run_logged() -> None:
    try:
        await run_in_threadpool(run)
    except HTTPException as err:
        log.warning("Backup not started: %s", err.detail)


async def scheduler() -> None:
    """Daily backups at backup_time. If the last one is over a day old
    (Home Assistant was off at night), catch up a few minutes after start."""
    if STATE != "mounted":
        return
    last_ok = _load().get("last_ok") or 0
    if time.time() - last_ok > 25 * 3600:
        await asyncio.sleep(5 * 60)
        await _run_logged()
    while True:
        await asyncio.sleep(max(1, (next_run() - datetime.now()).total_seconds()))
        await _run_logged()
