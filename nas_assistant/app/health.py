"""Disk health (SMART): warn before a disk breaks.

Every few hours each disk in use is asked for its SMART data (smartctl): overall verdict,
temperature, hours on, and the counters that grow before a failure (reallocated, pending
and uncorrectable sectors; for SSDs, wear and media errors). The Disks page shows it; a
disk that gets worse raises a Home Assistant notification, once per change.

USB enclosures pass SMART on only sometimes (with "-d sat"); when a disk can't be read,
its health is "unknown", never "good".
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from typing import Dict, List, Optional

import aiohttp

log = logging.getLogger("uvicorn.error")

CHECK_SECONDS = 6 * 3600
HOT_C = 55
_results: Dict[str, dict] = {}  # disk path -> last health
_notified: Dict[str, str] = {}  # disk path -> state already notified


_why: Dict[str, str] = {}  # device -> why it couldn't be read (for the log and the page)


def _smartctl(device: str) -> Optional[dict]:
    """SMART data as JSON; tries the plain way, then through a USB-SATA bridge."""
    for extra in ([], ["-d", "sat"], ["-d", "sat,12"]):
        try:
            out = subprocess.run(["smartctl", "-j", "-H", "-A", "-i", *extra, device],
                                 capture_output=True, text=True, timeout=30).stdout
            data = json.loads(out or "{}")
        except (OSError, ValueError, subprocess.TimeoutExpired) as err:
            _why[device] = str(err)
            continue
        if "smart_status" in data or "nvme_smart_health_information_log" in data:
            return data
        messages = (data.get("smartctl") or {}).get("messages") or []
        _why[device] = "; ".join(m.get("string", "") for m in messages)[:300] or "no SMART data"
    log.info("SMART of %s not readable: %s", device, _why.get(device))
    return None


def _attr(data: dict, *ids: int) -> int:
    table = (data.get("ata_smart_attributes") or {}).get("table") or []
    return sum(int((row.get("raw") or {}).get("value") or 0) for row in table if row.get("id") in ids)


def assess(data: Optional[dict]) -> dict:
    """A plain verdict: good, warning, failing or unknown, with the reasons."""
    if not data:
        return {"state": "unknown", "reasons": ["unreadable"]}
    reasons, state = [], "good"
    if not (data.get("smart_status") or {}).get("passed", True):
        state, reasons = "failing", ["smart_failed"]
    nvme = data.get("nvme_smart_health_information_log") or {}
    bad = {"reallocated": _attr(data, 5), "pending": _attr(data, 197), "uncorrectable": _attr(data, 198),
           "media_errors": int(nvme.get("media_errors") or 0)}
    for name, value in bad.items():
        if value:
            reasons.append(name)
            state = "failing" if state == "failing" or name in ("pending", "uncorrectable") else "warning"
    worn = int(nvme.get("percentage_used") or 0)
    if worn >= 90:
        reasons.append("worn")
        state = "failing" if state == "failing" else "warning"
    temperature = (data.get("temperature") or {}).get("current")
    if temperature and temperature >= HOT_C:
        reasons.append("hot")
        state = state if state == "failing" else "warning"
    return {"state": state, "reasons": reasons, "temperature": temperature,
            "hours": (data.get("power_on_time") or {}).get("hours"), "worn": worn or None,
            "model": data.get("model_name") or "", **{k: v for k, v in bad.items() if v}}


def check(disks: List[str], partitions: Optional[Dict[str, List[str]]] = None) -> Dict[str, dict]:
    """Read every disk now (slow: a few seconds each). With protection mode on only the
    partitions given to the add-on exist here: then the disk is asked through them."""
    for device in disks:
        nodes = [n for n in [device, *(partitions or {}).get(device, [])] if os.path.exists(n)]
        data = next((d for d in map(_smartctl, nodes) if d), None)
        result = assess(data)
        if not data:
            result["detail"] = next((_why[n] for n in nodes if n in _why), "device not available")
        result["checked"] = int(time.time())
        _results[device] = result
    return dict(_results)


def get(device: str) -> Optional[dict]:
    return _results.get(device)


async def _notify(device: str, model: str, result: dict) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return
    title = "NAS Assistant"
    reasons = ", ".join(result["reasons"])
    if result["state"] == "failing":
        message = f"The disk {model or device} may be failing ({reasons}). Copy what matters elsewhere and replace it."
    else:
        message = f"The disk {model or device} needs attention ({reasons}). See NAS Assistant → Disks."
    try:
        async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {token}"},
                                         timeout=aiohttp.ClientTimeout(total=10)) as session:
            await session.post("http://supervisor/core/api/services/persistent_notification/create",
                               json={"title": title, "message": message,
                                     "notification_id": f"nas_assistant_health_{abs(hash(device))}"})
    except (aiohttp.ClientError, TimeoutError):
        pass


async def watch(list_disks) -> None:
    """Check the disks in use now and then; tell Home Assistant when one gets worse."""
    await asyncio.sleep(60)  # let the add-on settle first
    while True:
        try:
            disks = list_disks()
            results = await asyncio.get_running_loop().run_in_executor(
                None, check, [d for d, _, _ in disks], {d: parts for d, _, parts in disks})
            for device, model, _ in disks:
                result = results.get(device) or {}
                state = result.get("state", "unknown")
                if state in ("warning", "failing") and _notified.get(device) != state:
                    log.warning("Disk %s health: %s %s", device, state, result.get("reasons"))
                    await _notify(device, model, result)
                _notified[device] = state
        except Exception as err:  # keep watching whatever happens
            log.warning("Disk health check: %s", err)
        await asyncio.sleep(CHECK_SECONDS)
