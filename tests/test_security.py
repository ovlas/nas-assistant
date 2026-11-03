"""Files can't run code in the browser; passes and links only do what they are for."""

import pytest

from conftest import NAS


@pytest.fixture(autouse=True)
def page():
    folder = NAS / "users" / "alice1"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "evil.html").write_text("<script>steal()</script>")
    (folder / "evil.svg").write_text("<svg onload=steal()></svg>")
    (folder / "doc.pdf").write_bytes(b"%PDF-1.4")


@pytest.mark.parametrize("name", ["evil.html", "evil.svg"])
def test_html_and_svg_are_never_shown_inline_and_always_sandboxed(client, alice, name):
    r = client.get("/api/download", headers=alice, params={"space": "personal", "path": name, "inline": 1})
    assert r.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_pdf_opens_in_the_browser(client, alice):
    r = client.get("/api/download", headers=alice, params={"space": "personal", "path": "doc.pdf", "inline": 1})
    assert r.headers["content-disposition"].startswith("inline")


def test_an_upload_pass_only_uploads(client, alice):
    token = client.post("/api/upload/session", headers=alice).json()["token"]
    as_pass = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/upload", headers=as_pass, params={"space": "personal", "name": "x.bin", "size": 1}).status_code == 200
    for url in ("/api/files?space=personal", "/api/download?space=personal&path=evil.html", "/api/me", "/api/trash"):
        assert client.get(url, headers=as_pass).status_code == 401, url
    assert client.get("/api/upload", headers={"Authorization": "Bearer upl_forged"},
                      params={"space": "personal", "name": "x.bin", "size": 1}).status_code == 401


def test_tv_links_only_answer_the_home_network(client):
    from nas_assistant.app import tv
    link = tv.link("http://192.168.1.2:8456", NAS / "users" / "alice1" / "doc.pdf").split(":8456")[1]
    assert client.get(link).status_code == 404  # the test client isn't on a home network
    assert client.get(link, headers={"CF-Connecting-IP": "1.2.3.4"}).status_code == 404
    assert client.get("/tv/not-a-token/x.jpg").status_code == 404


def test_wrong_tokens_are_slowed_down(client, monkeypatch):
    from nas_assistant.app import auth

    async def nobody(token):
        return None
    monkeypatch.setattr(auth, "_from_bearer", nobody)
    codes = [client.get("/api/me", headers={"Authorization": "Bearer wrong", "CF-Connecting-IP": "9.9.9.9"}).status_code
             for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[-1] == 429


def test_disk_health_verdicts():
    from nas_assistant.app import health
    assert health.assess(None)["state"] == "unknown"
    good = {"smart_status": {"passed": True}, "temperature": {"current": 35}, "power_on_time": {"hours": 1200}}
    assert health.assess(good)["state"] == "good"
    realloc = {**good, "ata_smart_attributes": {"table": [{"id": 5, "raw": {"value": 8}}]}}
    assert health.assess(realloc)["state"] == "warning"
    pending = {**good, "ata_smart_attributes": {"table": [{"id": 197, "raw": {"value": 2}}]}}
    assert health.assess(pending)["state"] == "failing"
    assert health.assess({"smart_status": {"passed": False}})["state"] == "failing"
    worn = {"smart_status": {"passed": True}, "nvme_smart_health_information_log": {"percentage_used": 95}}
    assert health.assess(worn)["state"] == "warning"
