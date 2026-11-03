"""Test setup: a fake NAS disk in a temporary folder, and a web client that comes in
like Ingress does (X-Remote-User-* headers from a trusted address)."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(tempfile.mkdtemp(prefix="nas-tests-"))
(ROOT / "nas").mkdir()
os.environ.update({
    "NAS_ROOT": str(ROOT / "nas"),
    "NAS_DISK_STATE": "mounted",
    "NAS_STORAGE_STATE": "none",
    "NAS_DEV_TRUSTED_IP": "testclient",  # the address of Starlette's test client
    "NAS_DEV_ADMINS": "admin1",
    "NAS_DEVICES_FILE": str(ROOT / "devices.json"),
    "NAS_KNOWN_DISKS_FILE": str(ROOT / "known.json"),
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from nas_assistant.app import main  # noqa: E402

NAS = ROOT / "nas"


def as_user(user_id: str) -> dict:
    return {"X-Remote-User-Id": user_id, "X-Remote-User-Name": user_id}


@pytest.fixture(scope="session")
def client():
    return TestClient(main.app)


@pytest.fixture
def alice():
    return as_user("alice1")


@pytest.fixture
def bob():
    return as_user("bob1")


@pytest.fixture
def admin():
    return as_user("admin1")
