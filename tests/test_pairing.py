"""Pairing the phone app: the QR code on the page."""

import json
import re

from conftest import NAS

from nas_assistant.app import devices, main


def test_the_qr_code_scales_to_its_box(client, alice):
    svg = client.post("/api/devices/pairing", headers=alice).json()["qr_svg"]
    # The page sizes the SVG with CSS: a fixed width/height without a viewBox crops the code.
    assert re.search(r'viewBox="0 0 \d+ \d+"', svg)
    assert not re.search(r'<svg[^>]* width=', svg)


def code_from(client, who, monkeypatch):
    monkeypatch.setattr(main, "PUBLIC_URL", "https://nas.example.com")
    return client.post("/api/devices/review", headers=who).json()["code"]


def pair(client, code):
    return client.post("/api/device/pair", json={"code": code, "name": "Review", "platform": "ios"})


def send(client, key, space="personal"):
    return client.post("/api/device/upload", headers={"Authorization": f"Bearer {key}"}, data={"space": space},
                       files={"file": ("IMG_1.jpg", b"photo")})


def test_the_review_code_is_for_administrators(client, alice, monkeypatch):
    monkeypatch.setattr(main, "PUBLIC_URL", "https://nas.example.com")
    assert client.post("/api/devices/review", headers=alice).status_code == 403
    assert client.get("/api/devices/review", headers=alice).status_code == 403
    assert client.delete("/api/devices/review", headers=alice).status_code == 403


def test_the_review_code_needs_the_public_address(client, admin, monkeypatch):
    monkeypatch.setattr(main, "PUBLIC_URL", "")
    assert client.post("/api/devices/review", headers=admin).status_code == 409


def test_the_review_code_works_many_times_for_its_own_user(client, admin, monkeypatch):
    code = code_from(client, admin, monkeypatch)
    first, second = pair(client, code), pair(client, code)
    assert first.status_code == second.status_code == 200
    assert first.json()["user"]["display_name"] == "App Review"
    assert send(client, first.json()["key"]).status_code == 200
    assert list((NAS / "users" / "app-review").rglob("IMG_1*.jpg"))


def test_a_review_phone_stays_out_of_the_family_space(client, admin, monkeypatch):
    key = pair(client, code_from(client, admin, monkeypatch)).json()["key"]
    assert send(client, key, space="family").status_code == 403


def test_ending_the_review_code_disconnects_its_phones(client, admin, monkeypatch):
    code = code_from(client, admin, monkeypatch)
    key = pair(client, code).json()["key"]
    assert client.delete("/api/devices/review", headers=admin).status_code == 200
    assert pair(client, code).status_code == 403
    assert send(client, key).status_code == 401
    assert client.get("/api/devices/review", headers=admin).json()["expires"] is None


def test_a_new_review_code_replaces_the_old_one(client, admin, monkeypatch):
    old = code_from(client, admin, monkeypatch)
    new = code_from(client, admin, monkeypatch)
    assert pair(client, old).status_code == 403
    assert pair(client, new).status_code == 200


def test_an_expired_review_code_is_refused(client, admin, monkeypatch):
    code = code_from(client, admin, monkeypatch)
    review = json.loads(devices.REVIEW_FILE.read_text())
    devices.REVIEW_FILE.write_text(json.dumps({**review, "expires": 1}))
    assert pair(client, code).status_code == 403
