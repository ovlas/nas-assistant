"""The Disks page: every disk the computer sees and what it is used for.

From here an administrator gives a free disk a role, and can change it later:
- backup: every night the NAS is copied onto it, on its own;
- storage: extra room, shown as one more folder in every space.
When its filesystem can't be used, the disk can be initialized, only on request.
Roles go through the Supervisor (the add-on edits its own `backup_device` /
`storage_device` options and restarts), so it works with protection mode on:
Home Assistant then grants access to those disks only.

Never initialized, whatever the request says: the NAS disk, any other
partition of the NAS disk's physical disk, and the Home Assistant system disk.
"""

import asyncio
import json
import logging
import time
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
from fastapi import HTTPException

from . import backup, disks, dlna, grants, health, storage

log = logging.getLogger("uvicorn.error")

SUPERVISOR = "http://supervisor"
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
NAS_DEVICE = os.environ.get("NAS_DEVICE", "")
# role -> (add-on option, device in use now, its state, its filesystem when unusable)
ROLES = {
    "backup": ("backup_device", os.environ.get("NAS_BACKUP_DEVICE", ""),
               os.environ.get("NAS_BACKUP_STATE", "none"), os.environ.get("NAS_BACKUP_FSTYPE", "")),
    "storage": ("storage_device", os.environ.get("NAS_STORAGE_DEVICE", ""),
                os.environ.get("NAS_STORAGE_STATE", "none"), os.environ.get("NAS_STORAGE_FSTYPE", "")),
}
BACKUP_FSTYPE = ROLES["backup"][3]
BY_ID = Path(os.environ.get("NAS_BY_ID_DIR", "/dev/disk/by-id"))
INIT_LABELS = {"nas": "NAS", "backup": "NAS Backup", "storage": "NAS Storage"}
MOUNTS = {"backup": Path(os.environ.get("NAS_BACKUP_ROOT", "/backup")),
          "storage": Path(os.environ.get("NAS_STORAGE_ROOT", "/storage"))}
# Device node -> by-id name, refreshed by the plug-and-play watcher: needed to remember a
# disk after it was unplugged, when its by-id link no longer exists.
_known_ids: Dict[str, str] = {}
# Disks ejected safely: their role is remembered so they can be put back with one tap.
EJECTED_FILE = Path(os.environ.get("NAS_EJECTED_FILE", "/data/ejected.json"))


def _ejected() -> Dict[str, dict]:
    try:
        return json.loads(EJECTED_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _save_ejected(data: Dict[str, dict]) -> None:
    EJECTED_FILE.write_text(json.dumps(data))


def _by_id() -> Dict[str, str]:
    """Device node -> its stable /dev/disk/by-id name (what the add-on options store)."""
    names = {}
    if BY_ID.is_dir():
        # Prefer the readable names (ata-…, usb-…, nvme-…) over wwn-… ones.
        for link in sorted(BY_ID.iterdir(), key=lambda p: p.name.startswith("wwn-")):
            names.setdefault(os.path.realpath(link), str(link))
    return names


def _can_read(device: str) -> bool:
    try:
        with open(device, "rb") as disk:
            return len(disk.read(4096)) > 0
    except OSError:
        return False


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


_counts: Dict[str, tuple] = {}  # data root -> (when, count)


def _nas_files(mount: Path) -> Optional[int]:
    """How many NAS Assistant files a disk holds (its users/ and family/ folders), cached a minute."""
    root = storage.data_root(mount, mount)
    cached = _counts.get(str(root))
    if cached and time.time() - cached[0] < 60:
        return cached[1]
    count = 0
    for top in ("users", "family"):
        stack = [str(root / top)]
        while stack:
            folder = stack.pop()
            for name, is_dir, *_ in storage._listing(folder):
                if is_dir:
                    stack.append(os.path.join(folder, name))
                else:
                    count += 1
    _counts[str(root)] = (time.time(), count)
    return count


def _top_folders(mount: Path) -> List[str]:
    """Names at the top of a disk and of its "NAS Assistant" folder (read only), to find data put
    there by hand or by an older version."""
    names = []
    for folder in (mount, mount / storage.DATA_FOLDER):
        try:
            names += [str(p.relative_to(mount)) for p in sorted(folder.iterdir())[:40]]
        except OSError:
            pass
    return names


def overview(include_system: bool = False) -> List[dict]:
    """Physical disks with their partitions and roles: nas, backup, storage or free.
    The Home Assistant system disk is left out, unless the safety checks ask for it."""
    by_id = _by_id()
    system = disks._system_devices()
    nas_disk = _parent(NAS_DEVICE) if NAS_DEVICE else ""
    result = []
    for dev in disks._lsblk():
        name = dev.get("name", "")
        if dev.get("type") != "disk" or name.startswith(disks.SKIP_NAMES) or "boot" in name:
            continue
        backup_device, storage_device = ROLES["backup"][1], ROLES["storage"][1]  # current, after an eject too
        in_use = (NAS_DEVICE, backup_device, storage_device)
        accessible = disks._readable(dev["path"]) if dev["path"] in in_use else None
        nodes = [c for c in dev.get("children") or [] if c.get("type") == "part"] or [dev]
        is_system = disks._is_system_disk(dev, system)
        if is_system and not include_system:
            continue
        parts = []
        for node in nodes:
            if node["path"] in in_use or os.access(node["path"], os.R_OK):
                disks._probe(node)
            role = ("system" if is_system else "nas" if node["path"] == NAS_DEVICE
                    else "backup" if node["path"] == backup_device
                    else "storage" if node["path"] == storage_device else "free")
            fstype = node.get("fstype") or (ROLES[role][3] if role in ROLES else "")
            parts.append({
                "path": node["path"],
                "id": by_id.get(node["path"], ""),
                "size": int(node.get("size") or 0),
                "fstype": fstype,
                "label": node.get("label") or "",
                "role": role,
                "usage": _usage(disks.NAS_ROOT) if role == "nas" and disks.state() == "mounted" else
                         _usage(backup.ROOT) if role == "backup" and backup.STATE == "mounted" else
                         _usage(Path(os.environ.get("NAS_STORAGE_ROOT", "/storage")))
                         if role == "storage" and ROLES["storage"][2] == "mounted" else None,
                "files": _nas_files(disks.NAS_ROOT) if role == "nas" and disks.state() == "mounted" else
                         _nas_files(storage.EXTRA_MOUNT) if role == "storage" and ROLES["storage"][2] == "mounted"
                         else None,
                "folders": _top_folders(disks.NAS_ROOT) if role == "nas" and disks.state() == "mounted" else
                           _top_folders(storage.EXTRA_MOUNT) if role == "storage" and ROLES["storage"][2] == "mounted"
                           else None,
                "state": ROLES[role][2] if role in ROLES else disks.state() if role == "nas" else "",
                # Ejected earlier from this role: offer to put it back.
                "was": _ejected().get(by_id.get(node["path"], ""), {}).get("role", "") if role == "free" else "",
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
            "health": health.get(dev["path"]),
            "usb_speed": _usb_speed(name),
            "partitions": parts,
        })
    return result


def _usb_speed(name: str) -> int:
    """Link speed in Mbit/s of a USB disk (480 = USB 2, 5000+ = USB 3), 0 if not USB or unknown."""
    path = Path(os.path.realpath(f"/sys/block/{name}"))
    for parent in path.parents:
        try:
            return int((parent / "speed").read_text().strip())
        except (OSError, ValueError):
            continue
    return 0


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
    grants.keep_on_next_stop()  # the disks it needs stay in the options
    try:
        await _supervisor("POST", "/addons/self/restart")
    except Exception as err:  # the restart itself cuts this request short
        log.info("Restart requested: %s", err)


async def allow_health() -> List[str]:
    """Ask Home Assistant for the whole disks NAS Assistant uses, to read their health only
    (with protection mode on it gets just the partitions). Restarts to apply."""
    in_use = {NAS_DEVICE, *(device for _, device, _, _ in ROLES.values())} - {""}
    disks_in_use = {_parent(d) for d in in_use}
    # The disk's own name (ata-…, as Home Assistant lists it), not the USB box's.
    names = sorted((p for p in BY_ID.iterdir() if not p.name.startswith(("wwn-", "nvme-eui."))
                    and "-part" not in p.name and os.path.realpath(p) in disks_in_use),
                   key=lambda p: (not p.name.startswith(("ata-", "nvme-")), p.name)) if BY_ID.is_dir() else []
    wanted, seen = [], set()
    for p in names:
        if os.path.realpath(p) not in seen:
            seen.add(os.path.realpath(p))
            wanted.append(str(p))
    if not wanted:
        raise HTTPException(400, "Disk not selectable")
    info = await _supervisor("GET", "/addons/self/info")
    options = dict(info.get("options") or {})
    options["smart_devices"] = wanted
    await grants.save_options(options)
    asyncio.get_running_loop().create_task(_restart_soon())
    return wanted


async def set_role(device_id: str, role: Optional[str]) -> None:
    """Give a disk the backup or storage role, move it from one role to the other,
    or (role None) stop using it. Role "nas" makes it the NAS disk, only while there is no
    working one (to swap disks). Nothing on the disk is erased. Restarts to apply."""
    if role not in (None, "nas", *ROLES):
        raise HTTPException(400, "Unknown role")
    if role == "nas" and disks.state() == "mounted":
        raise HTTPException(409, "The NAS disk is already configured")
    by_id = _by_id()
    current = {r: by_id.get(device, "") for r, (_, device, _, _) in ROLES.items()}
    disks_now = overview()
    free = {p["id"] for d in disks_now if not d["system"] for p in d["partitions"]
            if p["role"] == "free" and p["id"] and not p["same_disk_as_nas"]}
    free |= {d["id"] for d in disks_now if not d["system"] and d["id"]
             and all(p["role"] == "free" and not p["same_disk_as_nas"] for p in d["partitions"])}
    if device_id not in free and device_id not in current.values():
        raise HTTPException(400, "Disk not selectable")
    info = await _supervisor("GET", "/addons/self/info")
    options = dict(info.get("options") or {})
    for other, (option, _, _, _) in ROLES.items():
        # A disk has one role: take it away from wherever it is now.
        if options.get(option) and os.path.realpath(options[option]) == os.path.realpath(device_id):
            options.pop(option)
    if role:
        options["device" if role == "nas" else ROLES[role][0]] = device_id
    await grants.save_options(options)
    ejected = _ejected()
    if ejected.pop(device_id, None):
        _save_ejected(ejected)
    asyncio.get_running_loop().create_task(_restart_soon())


def _holders(path: Path) -> List[str]:
    """Processes with files open under a mount point, from /proc: what keeps a disk busy."""
    found = []
    prefix = str(path).rstrip("/") + "/"
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            name = Path(f"/proc/{pid}/comm").read_text().strip()
            links = [os.readlink(f"/proc/{pid}/cwd")]
            links += [os.readlink(f"/proc/{pid}/fd/{fd}") for fd in os.listdir(f"/proc/{pid}/fd")]
        except OSError:
            continue
        found += [f"{name}[{pid}] {link}" for link in links if link == str(path) or link.startswith(prefix)]
    return found


def _unmount(path: Path) -> bool:
    """Finish writes and unmount, giving requests still running a few seconds to end."""
    subprocess.run(["sync"], capture_output=True)
    for attempt in range(8):
        if subprocess.run(["umount", str(path)], capture_output=True).returncode == 0:
            return True
        time.sleep(0.75)
    log.warning("Can't unmount %s, files still open: %s", path, _holders(path) or "none found")
    return False


def _eject_nas() -> None:
    """Pause the NAS and unmount its disk so it can be unplugged. The configuration stays:
    when the disk is back, "Reactivate" restarts the add-on and everything mounts again."""
    if disks.state() != "mounted":
        raise HTTPException(400, "Disk not selectable")
    if backup._lock.locked():
        raise HTTPException(409, "A backup is running: wait for it to finish")
    disks.set_state("ejected")  # from now on, file requests answer "NAS disk not available"
    if not _unmount(disks.NAS_ROOT):
        disks.set_state("mounted")
        raise HTTPException(409, "The disk is in use: try again in a moment")


async def reactivate() -> None:
    """After the NAS disk is plugged back in: restart, so it mounts again."""
    asyncio.get_running_loop().create_task(_restart_soon())


async def eject(role: str) -> None:
    """Safely eject a disk: finish writes, unmount it. The backup and extra-storage disks also
    lose their role, remembered to put them back in one tap when plugged in again; the NAS
    disk pauses the NAS until it is reactivated."""
    if role == "nas":
        # The TV media server is paused on its own: it keeps files open on the disk.
        await dlna.halt()
        try:
            return await asyncio.get_running_loop().run_in_executor(None, _eject_nas)
        except HTTPException:
            dlna.resume()  # the disk stays: so do the TVs
            raise
    if role not in ROLES:
        raise HTTPException(400, "Unknown role")
    option, device, state, _ = ROLES[role]
    if state != "mounted":
        raise HTTPException(400, "Disk not selectable")
    if role == "backup" and backup._lock.locked():
        raise HTTPException(409, "A backup is running: wait for it to finish")
    try:
        if role == "storage":
            await dlna.halt()  # it shows the Family folder of this disk too
        await _eject_extra(role, option, device)
    finally:
        dlna.resume()  # back for the TVs, with the disks still there


async def _eject_extra(role: str, option: str, device: str) -> None:
    device_id = _by_id().get(device, "")
    info = await _supervisor("GET", "/addons/self/info")
    options = dict(info.get("options") or {})
    released = {k: v for k, v in options.items() if k != option}
    # Release the role first, so it is not given back on the next start while the disk is away.
    # If unmounting then fails, the role is given back.
    await grants.save_options(released)
    if not await asyncio.get_running_loop().run_in_executor(None, _unmount, MOUNTS[role]):
        await grants.save_options(options)
        raise HTTPException(409, "The disk is in use: try again in a moment")
    ejected = _ejected()
    ejected[device_id] = {"role": role, "at": int(time.time())}
    _save_ejected(ejected)
    # Effective right away, no restart needed.
    ROLES[role] = (option, "", "none", "")
    if role == "backup":
        backup.STATE = "none"
    else:
        storage.EXTRA_STATE = "none"


def _initialize(role: str, confirm: str) -> None:
    if confirm != disks.FORMAT_CONFIRM:
        raise HTTPException(400, "Formatting not confirmed")
    if role == "nas":
        # A NAS disk with no filesystem at all (run.sh checked): there is nothing on it to lose.
        device, state = NAS_DEVICE, disks.state()
    elif role in ROLES:
        _, device, state, _ = ROLES[role]
    else:
        raise HTTPException(400, "Unknown role")
    # Only a disk whose filesystem the NAS can't use: a working one is never erased from here.
    if not device or state != "uninitialized":
        raise HTTPException(400, "Disk not selectable")
    # Hard guards, independent of what the page shows.
    if role != "nas" and NAS_DEVICE and (os.path.realpath(device) == os.path.realpath(NAS_DEVICE)
                                         or _parent(device) == _parent(NAS_DEVICE)):
        raise HTTPException(400, "Disk not selectable")
    if not _can_read(device):
        # Not even readable (no access yet, or a failing disk): "no filesystem" can't be told apart.
        raise HTTPException(400, "Disk not selectable")
    if role == "nas" and subprocess.run(["blkid", "-p", "-s", "TYPE", "-o", "value", device],
                                        capture_output=True, text=True).stdout.strip():
        raise HTTPException(400, "Disk not selectable")
    if any(d["system"] and device in {d["path"], *(p["path"] for p in d["partitions"])}
           for d in overview(include_system=True)):
        raise HTTPException(400, "Disk not selectable")
    # The filesystem goes straight on the device the add-on was given (a partition, or a whole
    # new disk): with protection mode on, that is the only device it may write to.
    disks._run("wipefs", "-a", device)
    disks._run("mkfs.ext4", "-F", "-q", "-m", "0", "-L", INIT_LABELS[role], device)


async def initialize(role: str, confirm: str) -> None:
    await asyncio.get_running_loop().run_in_executor(None, _initialize, role, confirm)
    asyncio.get_running_loop().create_task(_restart_soon())
