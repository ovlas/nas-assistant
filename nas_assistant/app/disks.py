"""Find, format and mount the dedicated NAS disk.

The Home Assistant system disk (any disk carrying a `hassos-*` partition) is
never listed, so it can never be selected or formatted.
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
FORMAT_CONFIRM = "FORMATTA"
USABLE_FS = ("ext4", "exfat", "ntfs")
SKIP_NAMES = ("loop", "zram", "ram", "sr")
LSBLK_COLUMNS = "NAME,PATH,SIZE,TYPE,FSTYPE,LABEL,UUID,MODEL,VENDOR,TRAN,RM"

_state = os.environ.get("NAS_DISK_STATE", "mounted")
_lock = threading.Lock()


def state() -> str:
    return _state


def _run(*cmd: str, stdin: Optional[str] = None) -> str:
    try:
        return subprocess.run(cmd, input=stdin, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as err:
        raise HTTPException(500, f"{cmd[0]}: {err.stderr.strip() or err}")


def _lsblk() -> List[dict]:
    return json.loads(_run("lsblk", "-J", "-b", "-o", LSBLK_COLUMNS))["blockdevices"]


def _is_system_disk(dev: dict) -> bool:
    nodes = [dev, *(dev.get("children") or [])]
    return any((n.get("label") or "").startswith("hassos") for n in nodes)


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
    for dev in _lsblk() if devices is None else devices:
        name = dev.get("name", "")
        if dev.get("type") != "disk" or name.startswith(SKIP_NAMES) or "boot" in name:
            continue
        if _is_system_disk(dev):
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
            "partitions": parts,
        })
    return disks


def _mount(uuid: str) -> None:
    global _state
    device = _run("blkid", "-U", uuid).strip()
    NAS_ROOT.mkdir(parents=True, exist_ok=True)
    _run("mount", device, str(NAS_ROOT))
    CONFIG_FILE.write_text(json.dumps({"uuid": uuid}))
    _state = "mounted"


def _require_unconfigured() -> None:
    if _state == "mounted":
        raise HTTPException(409, "Il disco NAS è già configurato")


def use_partition(uuid: str) -> None:
    with _lock:
        _require_unconfigured()
        usable = {p["uuid"] for d in list_disks() for p in d["partitions"] if p["usable"]}
        if uuid not in usable:
            raise HTTPException(400, "Partizione non utilizzabile")
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
    raise HTTPException(500, "La nuova partizione non è comparsa")


def format_disk(disk_path: str, confirm: str) -> None:
    if confirm != FORMAT_CONFIRM:
        raise HTTPException(400, f"Scrivi {FORMAT_CONFIRM} per confermare")
    with _lock:
        _require_unconfigured()
        if disk_path not in {d["path"] for d in list_disks()}:
            raise HTTPException(400, "Disco non selezionabile")
        # One GPT partition spanning the whole disk, then ext4 labelled NAS.
        _run("sfdisk", "--wipe", "always", "--wipe-partitions", "always", disk_path,
             stdin="label: gpt\n,,L\n")
        part = _wait_for_partition(disk_path)
        _run("mkfs.ext4", "-F", "-q", "-m", "1", "-L", FS_LABEL, part)
        _mount(_run("blkid", "-s", "UUID", "-o", "value", part).strip())
