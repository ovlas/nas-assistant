"""The Disks page: every disk the computer sees and what it is used for.

From here an administrator can give a free disk the backup role and, when its
filesystem can't be used, initialize it. Changing the role goes through the
Supervisor (the add-on edits its own `backup_device` option and restarts), so
it also works with protection mode on: Home Assistant then grants access to
that disk only.

Never initialized, whatever the request says: the NAS disk, any other
partition of the NAS disk's physical disk, and the Home Assistant system disk.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
from fastapi import HTTPException

from . import backup, disks

log = logging.getLogger("uvicorn.error")

SUPERVISOR = "http://supervisor"
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
NAS_DEVICE = os.environ.get("NAS_DEVICE", "")
BACKUP_DEVICE = os.environ.get("NAS_BACKUP_DEVICE", "")
BACKUP_FSTYPE = os.environ.get("NAS_BACKUP_FSTYPE", "")
BY_ID = Path(os.environ.get("NAS_BY_ID_DIR", "/dev/disk/by-id"))
INIT_LABEL = "NAS Backup"


def _by_id() -> Dict[str, str]:
    """Device node -> its stable /dev/disk/by-id name (what the add-on options store)."""
    names = {}
    if BY_ID.is_dir():
        # Prefer the readable names (ata-…, usb-…, nvme-…) over wwn-… ones.
        for link in sorted(BY_ID.iterdir(), key=lambda p: p.name.startswith("wwn-")):
            names.setdefault(os.path.realpath(link), str(link))
    return names


def _parent(node: str) -> str:
    result = subprocess.run(["lsblk", "-no", "PKNAME", node], capture_output=True, text=True)
    parent = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    return f"/dev/{parent}" if parent else node


def _usage(root: Path) -> Optional[dict]:
    try:
        total, used, free = shutil.disk_usage(root)
        return {"total": total, "used": used, "free": free}
    except OSError:
        return None


def overview() -> List[dict]:
    """Physical disks with their partitions and roles: nas, backup, system or free."""
    by_id = _by_id()
    system = disks._system_devices()
    nas_disk = _parent(NAS_DEVICE) if NAS_DEVICE else ""
    result = []
    for dev in disks._lsblk():
        name = dev.get("name", "")
        if dev.get("type") != "disk" or name.startswith(disks.SKIP_NAMES) or "boot" in name:
            continue
        accessible = disks._readable(dev["path"]) if dev["path"] in (NAS_DEVICE, BACKUP_DEVICE) else None
        nodes = [c for c in dev.get("children") or [] if c.get("type") == "part"] or [dev]
        is_system = disks._is_system_disk(dev, system)
        parts = []
        for node in nodes:
            if node["path"] in (NAS_DEVICE, BACKUP_DEVICE) or os.access(node["path"], os.R_OK):
                disks._probe(node)
            role = ("system" if is_system else "nas" if node["path"] == NAS_DEVICE
                    else "backup" if node["path"] == BACKUP_DEVICE else "free")
            fstype = node.get("fstype") or (BACKUP_FSTYPE if role == "backup" else "")
            parts.append({
                "path": node["path"],
                "id": by_id.get(node["path"], ""),
                "size": int(node.get("size") or 0),
                "fstype": fstype,
                "label": node.get("label") or "",
                "role": role,
                "usage": _usage(disks.NAS_ROOT) if role == "nas" else
                         _usage(backup.ROOT) if role == "backup" and backup.STATE == "mounted" else None,
                # A partition of the NAS disk's physical disk is never offered for backups or initialized.
                "same_disk_as_nas": bool(nas_disk) and dev["path"] == nas_disk and role != "nas",
            })
        model = " ".join(filter(None, [(dev.get("vendor") or "").strip(), (dev.get("model") or "").strip()]))
        result.append({
            "path": dev["path"],
            "id": by_id.get(dev["path"], ""),
            "model": model or name,
            "size": int(dev.get("size") or 0),
            "transport": (dev.get("tran") or "").upper(),
            "system": is_system,
            "accessible": accessible,
            "partitions": parts,
        })
    return result


async def _supervisor(method: str, path: str, body: Optional[dict] = None) -> dict:
    if not TOKEN:
        raise HTTPException(503, "Home Assistant is not reachable")
    async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {TOKEN}"},
                                     timeout=aiohttp.ClientTimeout(total=20)) as session:
        async with session.request(method, f"{SUPERVISOR}{path}", json=body) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 300 or data.get("result") == "error":
                raise HTTPException(400, data.get("message") or "Home Assistant refused the change")
            return data.get("data") or {}


async def _restart_soon() -> None:
    """Restart the add-on after the response went out, so the page gets its answer."""
    await asyncio.sleep(1.5)
    try:
        await _supervisor("POST", "/addons/self/restart")
    except Exception as err:  # the restart itself cuts this request short
        log.info("Restart requested: %s", err)


async def set_backup_device(device_id: Optional[str]) -> None:
    """Give a free disk the backup role (or none), then restart to apply it."""
    if device_id:
        candidates = {p["id"] for d in overview() if not d["system"] for p in d["partitions"]
                      if p["role"] == "free" and p["id"] and not p["same_disk_as_nas"]}
        candidates |= {d["id"] for d in overview() if not d["system"] and d["id"]
                       and all(p["role"] == "free" and not p["same_disk_as_nas"] for p in d["partitions"])}
        if device_id not in candidates:
            raise HTTPException(400, "Disk not selectable")
    info = await _supervisor("GET", "/addons/self/info")
    options = dict(info.get("options") or {})
    if device_id:
        options["backup_device"] = device_id
    else:
        options.pop("backup_device", None)
    await _supervisor("POST", "/addons/self/options", {"options": options})
    asyncio.get_running_loop().create_task(_restart_soon())


def _initialize(confirm: str) -> None:
    if confirm != disks.FORMAT_CONFIRM:
        raise HTTPException(400, "Formatting not confirmed")
    device = BACKUP_DEVICE
    # Only a backup disk whose filesystem the NAS can't use: a working one is never erased from here.
    if not device or backup.STATE != "uninitialized":
        raise HTTPException(400, "Disk not selectable")
    # Hard guards, independent of what the page shows.
    if NAS_DEVICE and (os.path.realpath(device) == os.path.realpath(NAS_DEVICE) or _parent(device) == _parent(NAS_DEVICE)):
        raise HTTPException(400, "Disk not selectable")
    if any(d["system"] and device in {d["path"], *(p["path"] for p in d["partitions"])} for d in overview()):
        raise HTTPException(400, "Disk not selectable")
    # The filesystem goes straight on the device the add-on was given (a partition, or a whole
    # new disk): with protection mode on, that is the only device it may write to.
    disks._run("wipefs", "-a", device)
    disks._run("mkfs.ext4", "-F", "-q", "-m", "0", "-L", INIT_LABEL, device)


async def initialize(confirm: str) -> None:
    await asyncio.get_running_loop().run_in_executor(None, _initialize, confirm)
    asyncio.get_running_loop().create_task(_restart_soon())
