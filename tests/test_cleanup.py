"""Cleanup: only truly identical files are duplicates; the same photo saved again is similar."""

import io
import os
import random
import time

from PIL import Image, ImageDraw

from conftest import NAS


def photo(seed: int, size=(800, 600), quality=90) -> bytes:
    rnd = random.Random(seed)
    img = Image.new("RGB", size, (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    draw = ImageDraw.Draw(img)
    for _ in range(25):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        draw.ellipse((x, y, x + rnd.randrange(40, 300), y + rnd.randrange(40, 300)),
                     fill=(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def wait(client, who, space="personal"):
    client.post("/api/cleanup/scan", headers=who, data={"space": space})
    for _ in range(200):
        info = client.get("/api/cleanup", headers=who, params={"space": space}).json()
        if info["state"] != "scanning":
            return info
        time.sleep(0.05)
    raise AssertionError("scan didn't finish")


def test_duplicates_and_similar_photos(client, bob):
    home = NAS / "users" / "bob1" / "Pulizia"
    (home / "A").mkdir(parents=True, exist_ok=True)
    (home / "B").mkdir(parents=True, exist_ok=True)
    same = os.urandom(300_000)
    (home / "A" / "report.pdf").write_bytes(same)
    (home / "B" / "report copy.pdf").write_bytes(same)
    (home / "B" / "again.pdf").write_bytes(same)
    head = os.urandom(100_000)
    (home / "A" / "x.bin").write_bytes(head + b"one")  # same size and beginning, different end
    (home / "B" / "y.bin").write_bytes(head + b"two")
    big = photo(1)
    (home / "A" / "IMG_1.jpg").write_bytes(big)
    small = Image.open(io.BytesIO(big)).resize((400, 300))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=60)
    (home / "B" / "IMG_1 small.jpg").write_bytes(buf.getvalue())
    (home / "A" / "other.jpg").write_bytes(photo(99))

    info = wait(client, bob)
    assert info["state"] == "ready"
    dup_sets = [{f["name"] for f in g["files"]} for g in info["duplicates"]]
    assert {"report.pdf", "report copy.pdf", "again.pdf"} in dup_sets
    assert not any({"x.bin", "y.bin"} <= s for s in dup_sets)
    group = next(g for g in info["duplicates"] if "report.pdf" in {f["name"] for f in g["files"]})
    assert group["waste"] == 2 * 300_000
    similar_sets = [{f["name"] for f in g["files"]} for g in info["similar"]]
    assert any({"IMG_1.jpg", "IMG_1 small.jpg"} <= s for s in similar_sets)
    assert not any("other.jpg" in s for s in similar_sets)

    again = wait(client, bob)  # remembered fingerprints: same answer
    assert [{f["name"] for f in g["files"]} for g in again["duplicates"]] == dup_sets


def test_cleanup_only_looks_at_your_own_space(client, alice):
    assert client.get("/api/cleanup", headers=alice, params={"space": "../users/bob1"}).status_code == 400
