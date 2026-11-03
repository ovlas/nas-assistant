"""A disk that is missing never stops NAS Assistant from starting.

Home Assistant checks every disk named in the add-on options before it starts the add-on,
and refuses to start it if one is not plugged in. So the disks chosen here are kept in
/data/disks.json, and the options only name the disks plugged in now:

- on stop, the disks leave the options: a disk unplugged while NAS Assistant is off
  (or while the house is restarting) can't block it;
- on start, the chosen disks that are plugged in go back in the options. Home Assistant
  gives access to a disk only when the add-on starts (with protection mode off too: the
  disk is listed but can't be opened), so it then restarts once to get them.

Unplug any disk whenever you like, plug it back in: it is used again on its own.
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Set

log = logging.getLogger("uvicorn.error")

DISK_OPTIONS = ("device", "backup_device", "storage_device")
FILE = Path(os.environ.get("NAS_CHOSEN_DISKS_FILE", "/data/disks.json"))
# Written just before a restart NAS Assistant asks for: that stop keeps the disks it needs.
KEEP_FILE = Path(os.environ.get("NAS_KEEP_GRANTS_FILE", "/data/keep_grants"))


def _base(device_id: str) -> str:
    return re.sub(r"-part\d+$", "", device_id)


def chosen() -> Dict[str, object]:
    """The disks NAS Assistant uses, plugged in or not: option -> by-id name (smart_devices -> list)."""
    try:
        data = json.loads(FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _remember(options: dict) -> None:
    data = {k: options[k] for k in DISK_OPTIONS if options.get(k)}
    data["smart_devices"] = list(options.get("smart_devices") or [])
    try:
        FILE.write_text(json.dumps(data))
    except OSError as err:
        log.warning("Can't remember the disks: %s", err)


def _disk_values(options: dict) -> dict:
    found = {k: options[k] for k in DISK_OPTIONS if options.get(k)}
    found["smart_devices"] = sorted(options.get("smart_devices") or [])
    return found


def _tidy(disks: dict) -> dict:
    """One role per disk: an extra disk that is the NAS disk itself is dropped."""
    nas = disks.get("device")
    for option in ("backup_device", "storage_device"):
        if nas and disks.get(option) and _base(disks[option]) == _base(nas):
            log.warning("The disk for %s is the NAS disk itself: dropping it", option)
            disks.pop(option)
    return disks


def _present(info: dict) -> Set[str]:
    """Disk names Home Assistant would accept now (its own list), plus what this add-on sees."""
    names: Set[str] = set()
    for field in info.get("schema") or []:
        if isinstance(field, dict) and field.get("name") == "device":
            names |= set(field.get("options") or [])
    return names


def _granted(disks: dict, present: Set[str]) -> dict:
    """The chosen disks that are plugged in now, as add-on options."""
    here = lambda name: name in present or os.path.exists(name)  # noqa: E731
    granted = {k: v for k, v in disks.items() if k in DISK_OPTIONS and here(v)}
    granted["smart_devices"] = sorted(d for d in disks.get("smart_devices") or [] if here(d))
    return granted


async def save_options(options: dict) -> None:
    """Every change of the add-on options goes through here: the disks are remembered."""
    from .diskadmin import _supervisor
    _remember(options)
    await _supervisor("POST", "/addons/self/options", {"options": options})


def keep_on_next_stop() -> None:
    try:
        KEEP_FILE.write_text("1")
    except OSError:
        pass


async def on_start() -> bool:
    """Give back the chosen disks that are plugged in. True when the add-on restarts to get them."""
    from .diskadmin import _restart_soon, _supervisor
    if not os.environ.get("SUPERVISOR_TOKEN"):
        return False
    try:
        info = await _supervisor("GET", "/addons/self/info")
    except Exception as err:
        log.warning("Can't read the add-on options: %s", err)
        return False
    options = dict(info.get("options") or {})
    current = _disk_values(options)
    # What the options name wins (a choice made while NAS Assistant was off); what they
    # don't name is still chosen: the stop took it out.
    disks = {**chosen(), **{k: v for k, v in current.items() if v}}
    disks = _tidy(disks)
    _remember(disks)
    wanted = _granted(disks, _present(info))
    if wanted == current:
        return False
    for option in DISK_OPTIONS:
        options.pop(option, None)
    options.update(wanted)
    try:
        await _supervisor("POST", "/addons/self/options", {"options": options})
    except Exception as err:
        log.warning("Can't give the disks back: %s", err)
        return False
    added = {k: v for k, v in wanted.items() if v and current.get(k) != v}
    if not added:
        return False
    log.info("Getting access to the disks again: restarting once")
    keep_on_next_stop()
    asyncio.get_running_loop().create_task(_restart_soon())
    return True


async def on_stop() -> None:
    """Take the disks out of the options, so a disk unplugged meanwhile can't block the next start."""
    from .diskadmin import _supervisor
    if KEEP_FILE.exists():
        KEEP_FILE.unlink(missing_ok=True)
        return
    if not os.environ.get("SUPERVISOR_TOKEN"):
        return
    try:
        info = await asyncio.wait_for(_supervisor("GET", "/addons/self/info"), 5)
        options = dict(info.get("options") or {})
        _remember({**chosen(), **{k: v for k, v in _disk_values(options).items() if v}})
        for option in DISK_OPTIONS:
            options.pop(option, None)
        options["smart_devices"] = []
        await asyncio.wait_for(_supervisor("POST", "/addons/self/options", {"options": options}), 5)
    except Exception as err:
        log.warning("Can't take the disks out of the options: %s", err)
