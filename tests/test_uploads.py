"""Uploads: a file is kept only when it is whole and identical; nothing is ever overwritten."""

import hashlib
import os
import random

from conftest import NAS


def put_piece(client, who, name, data, start, end, body=None, **params):
    return client.put("/api/upload", headers=who, content=data[start:end] if body is None else body,
                      params={"space": "personal", "name": name, "offset": start, "size": len(data), "piece": 1, **params})


def plan(client, who, name, size, path=""):
    return client.get("/api/upload", headers=who, params={"space": "personal", "name": name, "size": size, "path": path}).json()


def missing(ranges, size):
    out, pos = [], 0
    for a, b in ranges:
        if a > pos:
            out.append((pos, a))
        pos = max(pos, b)
    if pos < size:
        out.append((pos, size))
    return out


def sha(data):
    return hashlib.sha256(data).hexdigest()


def test_pieces_in_any_order_cut_twice_and_late_make_an_identical_file(client, alice):
    for trial in range(3):
        name = f"big-{trial}.bin"
        data = os.urandom(3_000_007 + trial)
        piece = 250_000
        cuts = [(a, min(a + piece, len(data))) for a in range(0, len(data), piece)]
        random.shuffle(cuts)
        for a, b in cuts[:6]:
            assert put_piece(client, alice, name, data, a, b).json()["done"] is False
        a, b = cuts[6]  # a connection cut half way: what arrived is kept
        put_piece(client, alice, name, data, a, b, body=data[a:a + (b - a) // 3])
        put_piece(client, alice, name, data, *cuts[0])  # the same piece twice
        ranges = plan(client, alice, name, len(data))["ranges"]
        last = None
        for a, b in missing(ranges, len(data)):
            last = put_piece(client, alice, name, data, a, b).json()
        assert last["done"] is True
        assert put_piece(client, alice, name, data, *cuts[1]).json() == {"done": True, "received": 0}  # late copy
        folder = NAS / "users" / "alice1"
        assert sha((folder / name).read_bytes()) == sha(data)
        assert not [f for f in os.listdir(folder) if f.startswith(f".{name}")]


def test_a_file_is_not_kept_until_every_byte_arrived(client, alice):
    data = os.urandom(1_000_000)
    put_piece(client, alice, "holes.bin", data, 0, 400_000)
    put_piece(client, alice, "holes.bin", data, 600_000, 1_000_000)
    assert not (NAS / "users" / "alice1" / "holes.bin").exists()
    assert plan(client, alice, "holes.bin", len(data))["ranges"] == [[0, 400_000], [600_000, 1_000_000]]


def test_in_order_upload_checks_the_size_before_keeping_the_file(client, alice):
    data = os.urandom(500_000)
    params = {"space": "personal", "name": "seq.bin"}
    client.put("/api/upload", headers=alice, params={**params, "offset": 0}, content=data[:200_000])
    short = client.put("/api/upload", headers=alice, params={**params, "offset": 200_000, "final": 1, "size": len(data)},
                       content=data[200_000:400_000])  # the last 100 KB never arrived
    assert short.status_code == 409 and short.json()["detail"]["offset"] == 400_000
    assert not (NAS / "users" / "alice1" / "seq.bin").exists()
    done = client.put("/api/upload", headers=alice, params={**params, "offset": 400_000, "final": 1, "size": len(data)},
                      content=data[400_000:])
    assert done.status_code == 200
    assert sha((NAS / "users" / "alice1" / "seq.bin").read_bytes()) == sha(data)


def test_same_file_is_skipped_and_a_different_one_never_overwrites(client, alice):
    first = os.urandom(10_000)
    put_piece(client, alice, "IMG_0001.JPG", first, 0, len(first))
    assert plan(client, alice, "IMG_0001.JPG", len(first)) == {"name": "IMG_0001.JPG", "complete": True, "offset": len(first)}
    other = os.urandom(12_345)
    p = plan(client, alice, "IMG_0001.JPG", len(other))
    assert p["name"] == "IMG_0001 (2).JPG" and p["complete"] is False
    put_piece(client, alice, p["name"], other, 0, len(other))
    folder = NAS / "users" / "alice1"
    assert sha((folder / "IMG_0001.JPG").read_bytes()) == sha(first)
    assert sha((folder / "IMG_0001 (2).JPG").read_bytes()) == sha(other)


def test_bad_names_are_refused(client, alice):
    for name in ("../escape.txt", "a/b.txt", ".hidden", "..", "a\\b.txt"):
        r = client.put("/api/upload", headers=alice, content=b"x",
                       params={"space": "personal", "name": name, "offset": 0, "size": 1, "piece": 1})
        assert r.status_code in (400, 422), name
    assert not list(NAS.rglob("escape.txt"))


def test_the_gallery_comes_in_pages_with_month_counts(client, alice):
    import time as clock
    folder = NAS / "users" / "alice1" / "Foto"
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(25):
        (folder / f"P_{i:02d}.jpg").write_bytes(b"x")
        stamp = clock.time() - i * 40 * 86400
        os.utime(folder / f"P_{i:02d}.jpg", (stamp, stamp))
    first = client.get("/api/photos", headers=alice, params={"space": "personal", "offset": 0, "limit": 10}).json()
    assert len(first["items"]) == 10 and first["total"] >= 25 and sum(first["months"].values()) == first["total"]
    rest = client.get("/api/photos", headers=alice, params={"space": "personal", "offset": 10, "limit": 1000}).json()
    names = [i["name"] for i in first["items"] + rest["items"]]
    assert len(names) == first["total"] == len(set(names))  # every item once, none lost between pages
    taken = [i["taken"] for i in first["items"] + rest["items"]]
    assert taken == sorted(taken, reverse=True)  # newest first


def test_small_files_go_many_at_a_time_whole_and_never_overwriting(client, alice):
    import json
    files = {f"s_{i:03d}.txt": os.urandom(100 + i) for i in range(120)}
    items = [{"field": f"f{i}", "name": n, "path": "Batch/Sub", "size": len(d)} for i, (n, d) in enumerate(files.items())]
    items.append({"field": "short", "name": "short.txt", "path": "Batch/Sub", "size": 999})  # arrives cut
    upload = [(f"f{i}", (n, d)) for i, (n, d) in enumerate(files.items())] + [("short", ("short.txt", b"abc"))]
    r = client.post("/api/upload/batch", headers=alice, files=upload, data={"space": "personal", "items": json.dumps(items)})
    results = r.json()["results"]
    assert [x["state"] for x in results[:-1]] == ["done"] * 120 and results[-1]["state"] == "failed"
    folder = NAS / "users" / "alice1" / "Batch" / "Sub"
    assert all((folder / n).read_bytes() == d for n, d in files.items())
    assert not (folder / "short.txt").exists()
    again = client.post("/api/upload/batch", headers=alice, files=upload[:5],
                        data={"space": "personal", "items": json.dumps(items[:5])}).json()["results"]
    assert [x["state"] for x in again] == ["skipped"] * 5
    other = [("f0", ("s_000.txt", b"a different file"))]
    changed = client.post("/api/upload/batch", headers=alice, files=other, data={"space": "personal", "items": json.dumps(
        [{"field": "f0", "name": "s_000.txt", "path": "Batch/Sub", "size": 16}])}).json()["results"][0]
    assert changed == {"state": "done", "name": "s_000 (2).txt"} and (folder / "s_000.txt").read_bytes() == files["s_000.txt"]
