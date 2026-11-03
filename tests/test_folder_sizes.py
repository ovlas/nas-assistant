"""Folder sizes: everything a folder holds, at any depth; only in your own space."""

from conftest import NAS


def test_folder_sizes_count_everything_inside(client, bob):
    home = NAS / "users" / "bob1" / "Misure"
    (home / "Viaggi" / "2024" / "Mare").mkdir(parents=True, exist_ok=True)
    (home / "Vuota").mkdir(exist_ok=True)
    (home / "Viaggi" / "a.bin").write_bytes(b"x" * 1000)
    (home / "Viaggi" / "2024" / "b.bin").write_bytes(b"x" * 2000)
    (home / "Viaggi" / "2024" / "Mare" / "c.bin").write_bytes(b"x" * 3000)
    (home / "sciolto.txt").write_bytes(b"x" * 500)

    info = client.get("/api/folder-sizes", headers=bob, params={"space": "personal", "path": "Misure"}).json()
    assert info["folders"]["Viaggi"] == {"size": 6000, "files": 3}
    assert info["folders"]["Vuota"] == {"size": 0, "files": 0}
    assert (info["size"], info["files"]) == (6500, 4)

    # A file added deep inside counts at once.
    (home / "Viaggi" / "2024" / "Mare" / "d.bin").write_bytes(b"x" * 4000)
    info = client.get("/api/folder-sizes", headers=bob, params={"space": "personal", "path": "Misure"}).json()
    assert info["folders"]["Viaggi"] == {"size": 10000, "files": 4}


def test_folder_sizes_stay_private(client, alice):
    answer = client.get("/api/folder-sizes", headers=alice, params={"space": "personal", "path": "../bob1/Misure"})
    assert answer.status_code in (400, 403, 404)
    answer = client.get("/api/folder-sizes", headers=alice, params={"space": "disk:storage", "path": ""})
    assert answer.status_code in (403, 404)
