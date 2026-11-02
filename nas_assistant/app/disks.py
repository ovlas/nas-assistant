"""Find, format and mount the dedicated NAS disk.

The Home Assistant system disk is never listed, so it can never be selected
or formatted. It is recognised in two independent ways:
- a partition label or GPT partition name starting with `hassos`;
- the disk holding this add-on's own /data folder.
"""

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException

NAS_ROOT = Path(os.environ.get("NAS_ROOT", "/nas"))
CONFIG_FILE = Path(os.environ.get("NAS_DISK_CONFIG", "/data/disk.json"))
FS_LABEL = "NAS"
FORMAT_CONFIRM = "FORMAT"
USABLE_FS = ("ext4", "exfat", "ntfs")
SKIP_NAMES = ("loop", "zram", "ram", "sr")
MOUNT_CMD = os.environ.get("NAS_MOUNT_CMD", "/usr/local/bin/nas-mount")
LSBLK_COLUMNS = "NAME,PATH,MAJ:MIN,SIZE,TYPE,FSTYPE,LABEL,PARTLABEL,UUID,MODEL,VENDOR,TRAN,RM"
# Folders that live on the Home Assistant system disk.
SYSTEM_PATHS = ("/data",)

_state = os.environ.get("NAS_DISK_STATE", "mounted")
_lock = threading.Lock()


def state() -> str:
    return _state


def set_state(value: str) -> None:
    """E.g. "ejected": the NAS disk was unmounted on request; every file request pauses."""
    global _state
    _state = value


def _run(*cmd: str, stdin: Optional[str] = None) -> str:
    try:
        return subprocess.run(cmd, input=stdin, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as err:
        raise HTTPException(500, f"{cmd[0]}: {err.stderr.strip() or err}")


def _lsblk() -> List[dict]:
    return json.loads(_run("lsblk", "-J", "-b", "-o", LSBLK_COLUMNS))["blockdevices"]


def _probe(node: dict) -> None:
    """Fill filesystem details lsblk could not get (no udev database in the container)."""
    if node.get("fstype") and node.get("partlabel") is not None:
        return
    result = subprocess.run(["blkid", "-p", "-o", "export", node["path"]], capture_output=True, text=True)
    info = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    node["fstype"] = node.get("fstype") or info.get("TYPE", "")
    node["label"] = node.get("label") or info.get("LABEL", "")
    node["uuid"] = node.get("uuid") or info.get("UUID", "")
    node["partlabel"] = node.get("partlabel") or info.get("PART_ENTRY_NAME", "")


def _readable(path: str) -> bool:
    """False when HA keeps the add-on in protection mode: sysfs lists the disk
    but the container is not allowed to open it."""
    try:
        with open(path, "rb") as dev:
            dev.read(512)
        return True
    except OSError as err:
        print(f"Disk {path} is not readable: {err}", flush=True)
        return False


def _system_devices() -> set:
    devices = set()
    for path in SYSTEM_PATHS:
        if os.path.exists(path):
            dev = os.stat(path).st_dev
            devices.add(f"{os.major(dev)}:{os.minor(dev)}")
    return devices


def _is_system_disk(dev: dict, system_devices: set) -> bool:
    nodes = [dev, *(dev.get("children") or [])]
    for node in nodes:
        names = (node.get("label") or "", node.get("partlabel") or "")
        if any(name.startswith("hassos") for name in names) or node.get("maj:min") in system_devices:
            return True
    return False


def _partition(node: dict) -> dict:
    fstype = node.get("fstype") or ""
    return {
        "path": node["path"],
        "size": int(node.get("size") or 0),
        "fstype": fstype,
        "label": node.get("label") or "",
        "uuid": node.get("uuid") or "",
        "usable": fstype in USABLE_FS and bool(node.get("uuid")),
    }


def list_disks(devices: Optional[List[dict]] = None) -> List[dict]:
    disks = []
    system_devices = _system_devices()
    for dev in _lsblk() if devices is None else devices:
        name = dev.get("name", "")
        if dev.get("type") != "disk" or name.startswith(SKIP_NAMES) or "boot" in name:
            continue
        for node in [dev, *(dev.get("children") or [])]:
            _probe(node)
        if _is_system_disk(dev, system_devices):
            continue
        parts = [_partition(c) for c in dev.get("children") or [] if c.get("type") == "part"]
        if not parts and dev.get("fstype"):
            parts = [_partition(dev)]  # filesystem written on the whole disk
        model = " ".join(filter(None, [(dev.get("vendor") or "").strip(), (dev.get("model") or "").strip()]))
        disks.append({
            "path": dev["path"],
            "model": model or name,
            "size": int(dev.get("size") or 0),
            "transport": (dev.get("tran") or "").upper(),
            "removable": bool(dev.get("rm")),
            "accessible": _readable(dev["path"]),
            "partitions": parts,
        })
    return disks


def _mount(uuid: str) -> None:
    global _state
    device = _run("blkid", "-U", uuid).strip()
    NAS_ROOT.mkdir(parents=True, exist_ok=True)
    # Same helper as run.sh, so NTFS is never mounted read-only by the legacy driver.
    _run(MOUNT_CMD, device, str(NAS_ROOT))
    probe = NAS_ROOT / ".nas_assistant_write_test"
    try:
        probe.write_text("ok")
        probe.unlink()
    except OSError:
        subprocess.run(["umount", str(NAS_ROOT)], capture_output=True)
        raise HTTPException(500, "The disk mounts but is not writable")
    CONFIG_FILE.write_text(json.dumps({"uuid": uuid}))
    _state = "mounted"


def _require_unconfigured() -> None:
    if _state == "mounted":
        raise HTTPException(409, "The NAS disk is already configured")


def use_partition(uuid: str) -> None:
    with _lock:
        _require_unconfigured()
        usable = {p["uuid"] for d in list_disks() for p in d["partitions"] if p["usable"]}
        if uuid not in usable:
            raise HTTPException(400, "Partition not usable")
        _mount(uuid)


def _wait_for_partition(disk_path: str, timeout: float = 10) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for dev in _lsblk():
            if dev["path"] == disk_path:
                parts = [c["path"] for c in dev.get("children") or [] if c.get("type") == "part"]
                if parts:
                    return parts[0]
        time.sleep(0.5)
    raise HTTPException(500, "The new partition did not appear")


def format_disk(disk_path: str, confirm: str) -> None:
    if confirm != FORMAT_CONFIRM:
        raise HTTPException(400, "Formatting not confirmed")
    with _lock:
        _require_unconfigured()
        if disk_path not in {d["path"] for d in list_disks()}:
            raise HTTPException(400, "Disk not selectable")
        # One GPT partition spanning the whole disk, then ext4 labelled NAS.
        _run("sfdisk", "--wipe", "always", "--wipe-partitions", "always", disk_path,
             stdin="label: gpt\n,,L\n")
        part = _wait_for_partition(disk_path)
        _run("mkfs.ext4", "-F", "-q", "-m", "1", "-L", FS_LABEL, part)
        _mount(_run("blkid", "-s", "UUID", "-o", "value", part).strip())
