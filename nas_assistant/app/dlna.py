"""TVs of the house: a DLNA media server (ReadyMedia / minidlna) for the Family space.

Smart TVs (Samsung, LG, Sony, Philips…) find "NAS Assistant" among their sources and
browse the family photos, videos and music with the remote: by folder, or photos by
the date they were shot. DLNA has no password, so only the Family space is shared,
never anybody's private space. Read only: the TV can't change anything.

It is off until an administrator turns it on (the "dlna" option). The TVs find it on
the home network because the add-on uses the host network.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from . import disks, storage

log = logging.getLogger("uvicorn.error")

ENABLED = os.environ.get("NAS_DLNA", "false") == "true"
NAME = "NAS Assistant"
PORT = 8200
_process: Optional[asyncio.subprocess.Process] = None
_halted = False  # stopped on purpose (to eject a disk): not an error


def _folders() -> list:
    """The Family folder on every disk of the pool."""
    found = []
    for root in storage.disk_roots():
        family = root / "family"
        if family.is_dir():
            found.append(family)
    return found


def _config(work: Path) -> Path:
    lines = [f"media_dir={folder}" for folder in _folders()]
    lines += [
        f"friendly_name={NAME}",
        f"port={PORT}",
        f"db_dir={work}",
        f"log_dir={work}",
        "log_level=general,artwork,database,inotify,scanner,metadata,http,ssdp,tivo=warn",
        "inotify=yes",
        "notify_interval=60",
        "album_art_names=Cover.jpg/cover.jpg/Folder.jpg/folder.jpg",
        "strict_dlna=no",
        "serial=nas-assistant",
        "model_name=NAS Assistant",
    ]
    conf = work / "minidlna.conf"
    conf.write_text("\n".join(lines) + "\n")
    return conf


def status() -> dict:
    return {"enabled": ENABLED, "running": bool(_process and _process.returncode is None),
            "name": NAME, "folders": len(_folders()) if ENABLED else 0}


async def start() -> None:
    """Start the media server, if it is on and the NAS disk is there."""
    global _process, _halted
    if not ENABLED or disks.state() != "mounted":
        return
    _halted = False
    # Its database lives on the NAS disk: Home Assistant backups stay small.
    work = disks.NAS_ROOT / ".nas_assistant" / "dlna"
    work.mkdir(parents=True, exist_ok=True)
    try:
        conf = _config(work)
        _process = await asyncio.create_subprocess_exec(
            "minidlnad", "-f", str(conf), "-S", "-P", str(work / "minidlna.pid"),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    except OSError as err:
        log.warning("TV media server not started: %s", err)
        return
    log.info("TV media server on: the TVs of the house find \"%s\" (Family only)", NAME)
    _, err = await _process.communicate()
    if _process.returncode and not _halted:
        log.warning("TV media server stopped (%s): %s", _process.returncode, (err or b"").decode(errors="replace")[-500:])


def stop() -> None:
    if _process and _process.returncode is None:
        _process.terminate()


async def halt() -> None:
    """Stop the media server and wait until it let go of the disks: it keeps its database and
    the Family folders open, and a disk with open files can't be ejected."""
    global _halted
    if not _process or _process.returncode is not None:
        return
    _halted = True
    _process.terminate()
    try:
        await asyncio.wait_for(_process.wait(), 10)
    except asyncio.TimeoutError:
        _process.kill()
        await _process.wait()
    log.info("TV media server paused to eject a disk")


def resume() -> None:
    """Start it again with the disks that are there now (after an eject)."""
    if _halted:
        asyncio.get_running_loop().create_task(start())
