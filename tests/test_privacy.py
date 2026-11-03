"""Privacy: nobody reads or changes someone else's private space, whatever the path says."""


import pytest

from conftest import NAS


@pytest.fixture(autouse=True)
def bob_secret():
    folder = NAS / "users" / "bob1"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "secret.txt").write_text("bob only")


TRICKS = ["../bob1/secret.txt", "../../users/bob1/secret.txt", "/users/bob1/secret.txt",
          "..%2Fbob1%2Fsecret.txt", "./../bob1/secret.txt", "Docs/../../bob1/secret.txt"]


@pytest.mark.parametrize("path", TRICKS)
def test_no_path_reaches_another_users_space(client, alice, path):
    r = client.get("/api/download", headers=alice, params={"space": "personal", "path": path})
    assert r.status_code in (400, 404) and b"bob only" not in r.content


@pytest.mark.parametrize("path", TRICKS)
def test_no_path_deletes_or_renames_in_another_users_space(client, alice, path):
    client.delete("/api/files", headers=alice, params={"space": "personal", "path": path})
    client.post("/api/rename", headers=alice, data={"space": "personal", "path": path, "name": "mine.txt"})
    assert (NAS / "users" / "bob1" / "secret.txt").read_text() == "bob only"


def test_listing_shows_only_your_own_space(client, alice, bob):
    names = [e["name"] for e in client.get("/api/files", headers=alice, params={"space": "personal"}).json()["entries"]]
    assert "secret.txt" not in names
    names = [e["name"] for e in client.get("/api/files", headers=bob, params={"space": "personal"}).json()["entries"]]
    assert "secret.txt" in names


def test_unknown_spaces_are_refused(client, alice):
    for space in ("users", "../users", "bob1", "disk:nas", "disk:storage"):
        r = client.get("/api/files", headers=alice, params={"space": space})
        assert r.status_code in (400, 403, 404), space


def test_other_files_on_the_disk_are_for_administrators_and_hide_private_spaces(client, alice, admin):
    assert client.get("/api/disk/roots", headers=alice).status_code == 403
    assert client.get("/api/files", headers=alice, params={"space": "disk:nas"}).status_code == 403
    listed = client.get("/api/files", headers=admin, params={"space": "disk:nas"}).json()["entries"]
    assert not {"users", "family", ".nas_assistant"} & {e["name"] for e in listed}
    for path in ("users/bob1/secret.txt", "users", ".nas_assistant", "../etc/passwd"):
        r = client.get("/api/download", headers=admin, params={"space": "disk:nas", "path": path})
        assert r.status_code == 404, path


def test_a_shared_collection_never_takes_private_files(client, alice):
    (NAS / "users" / "alice1").mkdir(parents=True, exist_ok=True)
    (NAS / "users" / "alice1" / "private.jpg").write_bytes(b"x")
    col = client.post("/api/collections", headers=alice, data={"name": "Vacanze", "kind": "album", "shared": "1"}).json()
    r = client.post("/api/collections/items", headers=alice, data={"id": col["id"], "space": "personal", "path": "private.jpg"})
    assert r.status_code == 400


def test_headers_of_ingress_count_only_from_ingress():
    import asyncio
    from types import SimpleNamespace
    from nas_assistant.app import auth
    fake = SimpleNamespace(client=SimpleNamespace(host="192.168.1.50"),
                           headers={"X-Remote-User-Id": "admin1", "X-Remote-User-Name": "x"})
    assert asyncio.run(auth._from_ingress(fake)) is None


def test_without_login_nothing_is_readable(client):
    for url in ("/api/files?space=personal", "/api/download?space=family&path=x", "/api/me", "/api/disks/overview"):
        assert client.get(url).status_code == 401, url
