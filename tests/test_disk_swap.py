"""Unplug any disk, plug it back or put another one in: NAS Assistant always starts and goes on."""

import asyncio
import os

import pytest

import conftest  # noqa: F401  (sets up the environment first)
from nas_assistant.app import diskadmin, disks, grants, plugplay

FEATHER = "/dev/disk/by-id/ata-Feather_M13_512GB_AA28"
SAMSUNG = "/dev/disk/by-id/ata-Samsung_SSD_870_QVO_4TB_S5ST"


class FakeSupervisor:
    """The add-on options as the Supervisor keeps them, and which disks it can see."""

    def __init__(self, options, plugged, protected=True):
        self.options, self.plugged, self.protected = dict(options), set(plugged), protected
        self.restarts = 0

    async def __call__(self, method, path, body=None):
        if path == "/addons/self/info":
            return {"options": dict(self.options), "protected": self.protected,
                    "schema": [{"name": "device", "options": sorted(self.plugged)}]}
        if path == "/addons/self/options":
            new = body["options"]
            named = [new.get(k) for k in grants.DISK_OPTIONS if new.get(k)] + list(new.get("smart_devices") or [])
            missing = [d for d in named if d not in self.plugged]
            if missing:  # what Home Assistant does: a disk that isn't there is refused
                raise RuntimeError(f"Device '{missing[0]}' does not exist")
            self.options = dict(new)
            return {}
        if path == "/addons/self/restart":
            self.restarts += 1
            return {}
        raise AssertionError(path)

    def can_start(self):
        named = [self.options.get(k) for k in grants.DISK_OPTIONS if self.options.get(k)]
        return all(d in self.plugged for d in named + list(self.options.get("smart_devices") or []))


@pytest.fixture
def supervisor(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test")
    monkeypatch.setattr(grants, "FILE", tmp_path / "disks.json")
    monkeypatch.setattr(grants, "KEEP_FILE", tmp_path / "keep")

    def make(options, plugged, protected=True):
        fake = FakeSupervisor(options, plugged, protected)
        monkeypatch.setattr(diskadmin, "_supervisor", fake)

        async def restart_soon():  # as the real one, without its wait
            grants.keep_on_next_stop()
            await fake("POST", "/addons/self/restart")
        monkeypatch.setattr(diskadmin, "_restart_soon", restart_soon)
        return fake
    return make


def run(coro):
    async def go():
        result = await coro
        await asyncio.sleep(0)  # let a scheduled restart run
        await asyncio.sleep(0)
        return result
    return asyncio.run(go())


def test_a_disk_unplugged_while_off_never_blocks_the_start(supervisor):
    nas, extra = FEATHER + "-part1", SAMSUNG + "-part2"
    ha = supervisor({"device": nas, "storage_device": extra, "smart_devices": [FEATHER, SAMSUNG]},
                    {FEATHER, nas, SAMSUNG, extra})
    run(grants.on_stop())
    ha.plugged -= {FEATHER, nas}  # unplugged while NAS Assistant is off
    assert ha.can_start()
    assert grants.chosen()["device"] == nas  # still the NAS disk: it comes back on its own

    # Starts: the disk that is there is granted again, once.
    assert run(grants.on_start()) is True
    assert ha.options.get("storage_device") == extra and "device" not in ha.options
    assert ha.options["smart_devices"] == [SAMSUNG] and ha.restarts == 1
    run(grants.on_stop())  # the restart it asked for keeps the disks
    assert ha.options.get("storage_device") == extra
    assert run(grants.on_start()) is False  # nothing more to do: no restart loop

    # Plugged back in, next start: the NAS disk is the NAS disk again.
    run(grants.on_stop())
    ha.plugged |= {FEATHER, nas}
    assert run(grants.on_start()) is True
    assert ha.options["device"] == nas and ha.options["storage_device"] == extra


def test_no_restart_without_protection_mode(supervisor):
    nas = SAMSUNG + "-part2"
    ha = supervisor({"device": nas, "smart_devices": []}, {SAMSUNG, nas}, protected=False)
    run(grants.on_stop())
    assert "device" not in ha.options
    assert run(grants.on_start()) is False and ha.restarts == 0
    assert ha.options["device"] == nas


def test_the_same_disk_never_has_two_roles(supervisor):
    part = SAMSUNG + "-part2"
    ha = supervisor({"device": part, "storage_device": part, "smart_devices": []}, {SAMSUNG, part}, protected=False)
    run(grants.on_start())
    assert ha.options["device"] == part and "storage_device" not in ha.options
    assert "storage_device" not in grants.chosen()


def _fake_disk(monkeypatch, tmp_path, fstype, nas_state="missing"):
    by_id = tmp_path / "by-id"
    by_id.mkdir()
    node = tmp_path / "sdz1"
    node.write_text("")
    (by_id / "usb-New_Disk_123456789-part1").symlink_to(node)
    monkeypatch.setattr(diskadmin, "BY_ID", by_id)
    monkeypatch.setattr(disks, "state", lambda: nas_state)
    part = {"id": str(by_id / "usb-New_Disk_123456789-part1"), "path": str(node), "size": 10**12,
            "fstype": fstype, "role": "free", "same_disk_as_nas": False}
    monkeypatch.setattr(diskadmin, "overview", lambda: [
        {"id": str(by_id / "usb-New_Disk_123456789"), "system": False, "partitions": [part]}])
    taken = []

    async def set_role(device_id, role):
        taken.append((device_id, role))
    monkeypatch.setattr(diskadmin, "set_role", set_role)

    async def quiet(*_):
        return None
    monkeypatch.setattr(plugplay, "_notify", quiet)
    monkeypatch.setattr(plugplay, "_known", lambda: {})
    monkeypatch.setattr(diskadmin, "_ejected", lambda: {})
    return part, taken


def test_a_new_disk_in_place_of_the_missing_one_becomes_the_nas_disk(monkeypatch, tmp_path):
    part, taken = _fake_disk(monkeypatch, tmp_path, "exfat")
    assert run(plugplay._plugged({part["id"]})) is True
    assert taken == [(part["id"], "nas")]


def test_a_new_disk_is_only_announced_when_the_nas_disk_works(monkeypatch, tmp_path):
    part, taken = _fake_disk(monkeypatch, tmp_path, "exfat", nas_state="mounted")
    plugplay.new_disks.clear()
    assert run(plugplay._plugged({part["id"]})) is False
    assert taken == [] and plugplay.new_disks


def test_a_blank_disk_is_never_erased_on_its_own(monkeypatch, tmp_path):
    part, taken = _fake_disk(monkeypatch, tmp_path, "")
    assert run(plugplay._plugged({part["id"]})) is False
    assert taken == []


def test_a_disk_in_use_keeps_its_role(monkeypatch, tmp_path):
    part, taken = _fake_disk(monkeypatch, tmp_path, "ntfs")
    monkeypatch.setitem(diskadmin.ROLES, "storage", ("storage_device", os.path.realpath(part["path"]), "mounted", ""))
    monkeypatch.setattr(plugplay, "_known", lambda: {part["id"]: {"role": "nas", "at": 1}})
    assert run(plugplay._plugged({part["id"]})) is False
    assert taken == []
