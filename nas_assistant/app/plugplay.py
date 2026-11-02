"""Plug and play for disks.

Every few seconds the add-on looks at /dev/disk/by-id (the host's udev names):

- a disk it already knew (it had a role and was ejected, or unplugged) comes back:
  its role is restored on its own (the add-on restarts, as Home Assistant needs to
  grant access to a disk);
- a disk in use disappears without "Eject": it is unmounted and its role released
  (so Home Assistant can still start the add-on) and remembered for when it is back;
  for the NAS disk the NAS pauses;
- a disk never seen before appears: nothing is decided for the user. A Home
  Assistant notification and a banner in NAS Assistant ask what to use it for.

Nothing here ever formats a disk or replaces a working NAS disk.
"""

import asyncio
import logging
import os
import re
import subprocess
import time
from typing import Dict, Set

import aiohttp

from . import backup, diskadmin, disks, storage

log = logging.getLogger("uvicorn.error")

POLL_SECONDS = 5
# Disks plugged in since start that have no role yet: base by-id name -> details.
new_disks: Dict[str, dict] = {}
_lang = "en"

TEXTS = {
    "new": {"en": "New disk connected: {name}. Open NAS Assistant → Disks to choose what to use it for.",
            "it": "Nuovo disco collegato: {name}. Apri NAS Assistant → Dischi per scegliere come usarlo.",
            "es": "Nuevo disco conectado: {name}. Abre NAS Assistant → Discos para elegir cómo usarlo.",
            "fr": "Nouveau disque branché : {name}. Ouvrez NAS Assistant → Disques pour choisir son usage.",
            "de": "Neue Festplatte angeschlossen: {name}. Öffne NAS Assistant → Festplatten, um ihre Verwendung zu wählen."},
    "gone": {"en": "The disk {name} was unplugged without ejecting it. Plug it back in and NAS Assistant takes it back by itself.",
             "it": "Il disco {name} è stato staccato senza espellerlo. Ricollegalo e NAS Assistant lo riprende da solo.",
             "es": "El disco {name} se desconectó sin expulsarlo. Vuelve a conectarlo y NAS Assistant lo retoma solo.",
             "fr": "Le disque {name} a été débranché sans être éjecté. Rebranchez-le et NAS Assistant le reprend tout seul.",
             "de": "Die Festplatte {name} wurde ohne Auswerfen abgezogen. Schließe sie wieder an, NAS Assistant übernimmt sie selbst."},
}


def _ids() -> Set[str]:
    """Current by-id names of disks and partitions (wwn-/eui names left out: duplicates)."""
    if not diskadmin.BY_ID.is_dir():
        return set()
    return {str(p) for p in diskadmin.BY_ID.iterdir() if not p.name.startswith(("wwn-", "nvme-eui."))}


def _base(device_id: str) -> str:
    """The whole-disk name of a partition's by-id name."""
    return re.sub(r"-part\d+$", "", device_id)


def _label(device_id: str) -> str:
    """A readable disk name from its by-id name, e.g. usb-WD_Elements_2621_... -> WD Elements 2621."""
    name = os.path.basename(_base(device_id)).split("-", 1)[-1]
    name = re.sub(r"_[0-9A-Fa-f]{8,}.*$", "", name)  # drop the serial number
    return name.replace("_", " ").strip() or os.path.basename(device_id)


async def _notify(kind: str, device_id: str) -> None:
    """A Home Assistant notification, so a plugged disk is noticed even with NAS Assistant closed."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return
    message = TEXTS[kind].get(_lang, TEXTS[kind]["en"]).format(name=_label(device_id))
    try:
        async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {token}"},
                                         timeout=aiohttp.ClientTimeout(total=10)) as session:
            await session.post("http://supervisor/core/api/services/persistent_notification/create",
                               json={"title": "NAS Assistant", "message": message,
                                     "notification_id": f"nas_assistant_disk_{abs(hash(_base(device_id)))}"})
    except (aiohttp.ClientError, TimeoutError):
        pass


async def _language() -> None:
    global _lang
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return
    try:
        async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {token}"},
                                         timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("http://supervisor/core/api/config") as resp:
                _lang = ((await resp.json()).get("language") or "en")[:2]
    except (aiohttp.ClientError, TimeoutError, ValueError):
        pass


async def _release(option: str) -> None:
    info = await diskadmin._supervisor("GET", "/addons/self/info")
    options = {k: v for k, v in (info.get("options") or {}).items() if k != option}
    await diskadmin._supervisor("POST", "/addons/self/options", {"options": options})


async def _unplugged() -> None:
    """Disks in use whose device vanished: unmount, release the role, remember it."""
    by_id = diskadmin._by_id()
    nas = diskadmin.NAS_DEVICE
    if nas and disks.state() in ("mounted", "ejected") and not os.path.exists(nas):
        log.warning("The NAS disk was unplugged: pausing the NAS")
        subprocess.run(["umount", "-l", str(disks.NAS_ROOT)], capture_output=True)
        disks.set_state("missing")
        device_id = diskadmin._known_ids.get(nas, by_id.get(nas, ""))
        await _remember_and_release("nas", "device", device_id)
    for role, (option, device, state, _) in list(diskadmin.ROLES.items()):
        if device and state in ("mounted", "uninitialized", "missing") and not os.path.exists(device):
            log.warning("The %s disk was unplugged without ejecting it", role)
            subprocess.run(["umount", "-l", str(diskadmin.MOUNTS[role])], capture_output=True)
            device_id = diskadmin._known_ids.get(device, "")
            diskadmin.ROLES[role] = (option, "", "none", "")
            if role == "backup":
                backup.STATE = "none"
            else:
                storage.EXTRA_STATE = "none"
            await _remember_and_release(role, option, device_id)


async def _remember_and_release(role: str, option: str, device_id: str) -> None:
    if device_id:
        ejected = diskadmin._ejected()
        ejected[device_id] = {"role": role, "at": int(time.time()), "unplugged": True}
        diskadmin._save_ejected(ejected)
        await _notify("gone", device_id)
    try:
        # Without the option Home Assistant can still start the add-on while the disk is away.
        await _release(option)
    except Exception as err:
        log.warning("Couldn't release the %s option: %s", option, err)


async def _plugged(added: Set[str]) -> None:
    """Known disks get their role back on their own; new ones are announced."""
    remembered = diskadmin._ejected()
    for device_id in sorted(added):
        entry = remembered.get(device_id)
        if not entry:
            continue
        role = entry["role"]
        if role == "nas":
            if disks.state() == "mounted":
                continue  # never replace a working NAS disk
            log.info("The NAS disk is back (%s): taking it back", device_id)
            info = await diskadmin._supervisor("GET", "/addons/self/info")
            options = dict(info.get("options") or {})
            options["device"] = device_id
            await diskadmin._supervisor("POST", "/addons/self/options", {"options": options})
            remembered.pop(device_id, None)
            diskadmin._save_ejected(remembered)
            asyncio.get_running_loop().create_task(diskadmin._restart_soon())
            return
        if diskadmin.ROLES[role][2] in ("none", "missing"):
            log.info("The %s disk is back (%s): restoring its role", role, device_id)
            await diskadmin.set_role(device_id, role)
            return
    # The NAS disk paused with "Eject" and plugged back in: reactivate on its own.
    if disks.state() == "ejected" and diskadmin.NAS_DEVICE and os.path.exists(diskadmin.NAS_DEVICE):
        log.info("The ejected NAS disk is back: reactivating")
        asyncio.get_running_loop().create_task(diskadmin._restart_soon())
        return
    for base in sorted({_base(i) for i in added}):
        if any(_base(i) == base for i in remembered) or base in new_disks:
            continue
        new_disks[base] = {"id": base, "name": _label(base), "at": int(time.time())}
        log.info("New disk connected: %s", base)
        await _notify("new", base)


def forget_new(device_id: str) -> None:
    new_disks.pop(_base(device_id), None)


async def watch() -> None:
    await _language()
    known = _ids()
    diskadmin._known_ids = diskadmin._by_id()
    # A remembered disk already plugged in while the add-on was stopped.
    await _plugged({i for i in known if i in diskadmin._ejected()})
    while True:
        await asyncio.sleep(POLL_SECONDS)
        try:
            now = _ids()
            added, gone = now - known, known - now
            known = now
            if gone:
                for i in gone:
                    new_disks.pop(_base(i), None)
                await _unplugged()
            # Names of what is plugged in now: once a disk is gone, its link is gone too.
            diskadmin._known_ids = diskadmin._by_id()
            if added:
                await _plugged(added)
        except Exception as err:  # keep watching whatever happens
            log.warning("Disk watch: %s", err)
