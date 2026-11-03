"""Plug and play for disks.

Every few seconds the add-on looks at /dev/disk/by-id (the host's udev names):

- a disk it already knew (it ever had a role) comes back: it is taken back on its
  own (the add-on restarts, as Home Assistant needs to grant access to a disk). An
  old NAS disk becomes the NAS disk again if there is none, otherwise it joins the
  pool as extra storage, so its files show up again;
- a disk in use disappears without "Eject": it is unmounted and its role released
  (so Home Assistant can still start the add-on) and remembered for when it is back;
  for the NAS disk the NAS pauses;
- a disk never seen before appears while there is no NAS disk (it was swapped for this
  one): it becomes the NAS disk on its own, as it is (only a "NAS Assistant" folder is
  added). The old one, if it ever comes back, joins as extra storage with its files;
- a disk never seen before appears otherwise: nothing is decided for the user. A Home
  Assistant notification and a banner in NAS Assistant ask what to use it for.

A disk in use keeps its role: it is never taken for another one. Nothing here ever
formats a disk or replaces a working NAS disk.
"""

import asyncio
import logging
import os
import re
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Set

import aiohttp

from . import backup, diskadmin, disks, grants, storage

log = logging.getLogger("uvicorn.error")

POLL_SECONDS = 5
# Every disk that ever had a role here: by-id name -> {"role", "at"}.
KNOWN_FILE = Path(os.environ.get("NAS_KNOWN_DISKS_FILE", "/data/known_disks.json"))
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
    "adopted": {"en": "New disk connected: {name}. There was no NAS disk, so NAS Assistant now uses this one. If the old disk comes back, its files show up again too.",
                "it": "Nuovo disco collegato: {name}. Mancava il disco del NAS, quindi NAS Assistant ora usa questo. Se ricolleghi quello vecchio, tornano anche i suoi file.",
                "es": "Nuevo disco conectado: {name}. Faltaba el disco del NAS, así que NAS Assistant usa ahora este. Si vuelves a conectar el antiguo, sus archivos también vuelven.",
                "fr": "Nouveau disque branché : {name}. Le disque du NAS manquait, NAS Assistant utilise donc celui-ci. Si l'ancien revient, ses fichiers reviennent aussi.",
                "de": "Neue Festplatte angeschlossen: {name}. Die NAS-Festplatte fehlte, also nutzt NAS Assistant jetzt diese. Kommt die alte zurück, sind auch ihre Dateien wieder da."},
    "back": {"en": "The disk {name} is connected again: its files are available again.",
             "it": "Il disco {name} è di nuovo collegato: i suoi file sono di nuovo disponibili.",
             "es": "El disco {name} vuelve a estar conectado: sus archivos están disponibles de nuevo.",
             "fr": "Le disque {name} est de nouveau branché : ses fichiers sont de nouveau disponibles.",
             "de": "Die Festplatte {name} ist wieder angeschlossen: ihre Dateien sind wieder verfügbar."},
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
    name = re.sub(r"(-\d+:\d+)$", "", name)
    name = re.sub(r"_(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{8,}$", "", name)  # drop the serial number
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
    # Disks given only for their health go too when they are gone: else the add-on can't start.
    options["smart_devices"] = [d for d in options.get("smart_devices") or [] if os.path.exists(d)]
    await grants.save_options(options)


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


def _bases_in_use() -> Set[str]:
    """The whole-disk names of the disks NAS Assistant uses now (any of their names)."""
    in_use = {diskadmin.NAS_DEVICE, *(device for _, device, _, _ in diskadmin.ROLES.values())} - {""}
    if not diskadmin.BY_ID.is_dir():
        return set()
    return {_base(str(p)) for p in diskadmin.BY_ID.iterdir() if os.path.realpath(p) in in_use}


USABLE = ("ext4", "exfat", "ntfs", "ntfs3")


async def _adopt(bases: Set[str]) -> bool:
    """No NAS disk and a disk never used here: make it the NAS disk, as it is. A disk with no
    filesystem is only announced: making it usable erases it, so the user confirms that."""
    if disks.state() not in ("missing", "unconfigured") or not bases:
        return False
    found = []
    for disk in diskadmin.overview():
        if disk["system"] or _base(disk["id"] or "") not in bases:
            continue
        found += [p for p in disk["partitions"] if p["role"] == "free" and p["id"]
                  and (p["fstype"] or "").lower() in USABLE and not p["same_disk_as_nas"]]
    if not found:
        return False
    part = max(found, key=lambda p: p["size"])
    log.info("No NAS disk and a new disk (%s): using it as the NAS disk", part["id"])
    await diskadmin.set_role(part["id"], "nas")
    forget_new(part["id"])
    await _notify("adopted", part["id"])
    return True


async def _plugged(added: Set[str]) -> bool:
    """Known disks get their role back on their own; new ones are announced. True when one
    was taken (NAS Assistant then restarts)."""
    remembered = diskadmin._ejected()
    known = _known()
    busy = _bases_in_use()
    added = {i for i in added if _base(i) not in busy}  # a disk in use keeps its role
    for device_id in sorted(added):
        entry = remembered.get(device_id) or known.get(device_id)
        if not entry:
            continue
        role = _comeback_role(entry["role"])
        if not role:
            continue  # its place is taken: never replace a disk in use
        await _notify("back", device_id)
        if role == "nas":
            log.info("The NAS disk is back (%s): taking it back", device_id)
            info = await diskadmin._supervisor("GET", "/addons/self/info")
            options = dict(info.get("options") or {})
            options["device"] = device_id
            await grants.save_options(options)
            remembered.pop(device_id, None)
            diskadmin._save_ejected(remembered)
            asyncio.get_running_loop().create_task(diskadmin._restart_soon())
            return True
        log.info("A known disk is back (%s): using it as %s", device_id, role)
        await diskadmin.set_role(device_id, role)
        return True
    # The NAS disk paused with "Eject" and plugged back in: reactivate on its own.
    if disks.state() == "ejected" and diskadmin.NAS_DEVICE and os.path.exists(diskadmin.NAS_DEVICE):
        log.info("The ejected NAS disk is back: reactivating")
        asyncio.get_running_loop().create_task(diskadmin._restart_soon())
        return True
    fresh = {_base(i) for i in added} - {_base(i) for i in (*remembered, *known)}
    if await _adopt(fresh):
        return True
    for base in sorted(fresh):
        if base in new_disks:
            continue
        new_disks[base] = {"id": base, "name": _label(base), "at": int(time.time())}
        log.info("New disk connected: %s", base)
        await _notify("new", base)
    return False


def _known() -> Dict[str, dict]:
    try:
        return json.loads(KNOWN_FILE.read_text())
    except (OSError, ValueError):
        return {}


def remember_current() -> None:
    """Note every by-id name of the disks in use now, with their role."""
    known = _known()
    in_use = {diskadmin.NAS_DEVICE: "nas"} if disks.state() == "mounted" and diskadmin.NAS_DEVICE else {}
    for role, (_, device, state, _) in diskadmin.ROLES.items():
        if device and state == "mounted":
            in_use[device] = role
    links = [(str(p), os.path.realpath(p)) for p in diskadmin.BY_ID.glob("*")] if diskadmin.BY_ID.is_dir() else []
    for link, real in links:
        if real in in_use:
            # All the names of one disk share a group, so an unplugged disk is listed once.
            group = min(_base(other) for other, r in links if r == real)
            known[link] = {"role": in_use[real], "at": int(time.time()), "group": group}
    try:
        KNOWN_FILE.write_text(json.dumps(known))
    except OSError:
        pass


def _comeback_role(role: str) -> str:
    """Where a known disk goes back: its old role if free; an old NAS disk joins as extra storage
    when another NAS disk is working; "" when its place is taken."""
    if role == "nas":
        if disks.state() != "mounted":
            return "nas"
        return "storage" if diskadmin.ROLES["storage"][2] in ("none", "missing") else ""
    return role if diskadmin.ROLES[role][2] in ("none", "missing") else ""


def away() -> List[dict]:
    """Disks that had a role here and are not plugged in now: the Disks page keeps showing them,
    so nobody wonders where their files went."""
    present = _ids()
    groups: Dict[str, dict] = {}
    known = _known()
    for device_id, entry in {**known, **diskadmin._ejected()}.items():
        group = entry.get("group") or known.get(device_id, {}).get("group") or _base(device_id)
        current = groups.setdefault(group, {"ids": set(), "role": entry["role"], "at": 0})
        current["ids"].add(device_id)
        if entry.get("at", 0) >= current["at"]:
            current["role"], current["at"] = entry["role"], entry.get("at", 0)
    result = []
    for group, entry in groups.items():
        if entry["ids"] & present or any(_base(i) in {_base(p) for p in present} for i in entry["ids"]):
            continue
        # The ata- name carries the disk model; a USB enclosure's name often doesn't.
        name_id = sorted(entry["ids"], key=lambda i: not os.path.basename(i).startswith("ata-"))[0]
        result.append({"id": group, "name": _label(name_id), "role": entry["role"], "at": entry["at"]})
    return sorted(result, key=lambda d: -d["at"])


def forget_new(device_id: str) -> None:
    new_disks.pop(_base(device_id), None)


async def watch() -> None:
    await _language()
    known = _ids()
    diskadmin._known_ids = diskadmin._by_id()
    remember_current()
    # A known disk already plugged in while the add-on was stopped, or, with no NAS disk,
    # a new one put in its place.
    remembered = {*diskadmin._ejected(), *_known()}
    busy = _bases_in_use()
    taken = await _plugged({i for i in known if i in remembered and _base(i) not in busy})
    if not taken and disks.state() == "missing":
        await _adopt({_base(i) for i in known if _base(i) not in busy} - {_base(i) for i in remembered})
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
