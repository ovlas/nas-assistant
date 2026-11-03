"""Downloads: direct links (resumable), whole folders as a zip identical to the files."""

import io
import os
import zipfile

from conftest import NAS


def link(client, who, path, space="personal"):
    return client.post("/api/download/link", headers=who, data={"space": space, "path": path}).json()


def test_a_file_link_downloads_and_resumes(client, alice):
    folder = NAS / "users" / "alice1"
    folder.mkdir(parents=True, exist_ok=True)
    data = os.urandom(300_000)
    (folder / "film.mov").write_bytes(data)
    got = link(client, alice, "film.mov")
    assert got["folder"] is False and got["name"] == "film.mov"
    url = f"/dl/{got['token']}/film.mov"
    assert client.get(url).content == data  # no login needed: the link is the key
    part = client.get(url, headers={"Range": "bytes=100000-199999"})
    assert part.status_code == 206 and part.content == data[100_000:200_000]


def test_a_folder_comes_as_a_zip_with_every_file_identical(client, alice):
    base = NAS / "users" / "alice1" / "Vacanze"
    (base / "Giorno 1").mkdir(parents=True, exist_ok=True)
    files = {"Vacanze/a.jpg": os.urandom(50_000), "Vacanze/Giorno 1/b.mov": os.urandom(120_000)}
    for name, data in files.items():
        (NAS / "users" / "alice1" / name).write_bytes(data)
    (base / ".DS_Store").write_bytes(b"hidden")
    got = link(client, alice, "Vacanze")
    assert got["folder"] is True and got["name"] == "Vacanze.zip"
    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/dl/{got['token']}/Vacanze.zip").content))
    assert archive.testzip() is None
    assert {n: archive.read(n) for n in archive.namelist()} == files


def test_links_are_personal_and_expire_unknown(client, alice, bob):
    (NAS / "users" / "bob1").mkdir(parents=True, exist_ok=True)
    (NAS / "users" / "bob1" / "private.pdf").write_bytes(b"bob")
    r = client.post("/api/download/link", headers=alice, data={"space": "personal", "path": "../bob1/private.pdf"})
    assert r.status_code in (400, 404)
    assert client.get("/dl/not-a-real-token/x.pdf").status_code == 404


def test_upload_into_subfolders_keeps_the_structure_and_never_into_hidden_ones(client, alice):
    data = os.urandom(70_000)
    params = {"space": "personal", "name": "c.jpg", "offset": 0, "size": len(data), "piece": 1}
    r = client.put("/api/upload", headers=alice, content=data, params={**params, "path": "Album/Sub/Deep"})
    assert r.json()["done"] is True
    assert (NAS / "users" / "alice1" / "Album" / "Sub" / "Deep" / "c.jpg").read_bytes() == data
    for path in (".nas_assistant", "Album/.hidden", ".trash/x"):
        r = client.put("/api/upload", headers=alice, content=data, params={**params, "path": path})
        assert r.status_code == 400, path


def test_big_files_go_whole_and_in_pieces_across_blocks(client, alice):
    """Files go out 1 MB at a time: a big file, and pieces that cross those blocks, arrive intact."""
    folder = NAS / "users" / "alice1"
    data = os.urandom(3 * 1024 * 1024 + 12345)
    (folder / "grande.mp4").write_bytes(data)
    url = f"/dl/{link(client, alice, 'grande.mp4')['token']}/grande.mp4"
    assert client.get(url).content == data
    start, end = 1024 * 1024 - 10, 2 * 1024 * 1024 + 10  # across two block edges
    part = client.get(url, headers={"Range": f"bytes={start}-{end}"})
    assert part.status_code == 206 and part.content == data[start:end + 1]
    tail = client.get(url, headers={"Range": "bytes=-100"})
    assert tail.content == data[-100:]
