"""What comes back from the trash is again in the collections and favorites it was in."""

import json

from conftest import NAS


def _collection(client, user, name, shared="0"):
    return client.post("/api/collections", headers=user, data={"name": name, "kind": "album", "shared": shared}).json()["id"]


def _add(client, user, cid, space, path):
    r = client.post("/api/collections/items", headers=user, data={"id": cid, "space": space, "path": path})
    assert r.status_code == 200


def _favorite(client, user, space, path):
    assert client.post("/api/favorites", headers=user, data={"space": space, "path": path, "favorite": "1"}).status_code == 200


def _in_collection(client, user, cid):
    return {i["path"] for i in client.get("/api/collections/items", headers=user, params={"id": cid}).json()["items"]}


def _favorites(client, user, space):
    return {e["path"] for e in client.get("/api/favorites", headers=user, params={"space": space}).json()["entries"]}


def _trash(client, user, space, path):
    r = client.delete("/api/files", headers=user, params={"space": space, "path": path})
    assert r.status_code == 200
    return r.json()["id"]


def _restore(client, user, item_id):
    r = client.post("/api/trash/restore", headers=user, data={"id": item_id})
    assert r.status_code == 200
    return r.json()


def _alice_file(rel):
    file = NAS / "users" / "alice1" / rel
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"x")


def _family_file(rel):
    file = NAS / "family" / rel
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"x")


def test_a_restored_file_is_back_in_its_collections_and_favorites(client, alice):
    _alice_file("links_a.jpg")
    cid = _collection(client, alice, "Links A")
    _add(client, alice, cid, "personal", "links_a.jpg")
    _favorite(client, alice, "personal", "links_a.jpg")

    item = _trash(client, alice, "personal", "links_a.jpg")
    assert _in_collection(client, alice, cid) == set()
    assert "links_a.jpg" not in _favorites(client, alice, "personal")

    _restore(client, alice, item)
    assert _in_collection(client, alice, cid) == {"links_a.jpg"}
    assert "links_a.jpg" in _favorites(client, alice, "personal")


def test_a_restored_folder_brings_back_what_is_inside(client, alice):
    _alice_file("links_dir/one.jpg")
    _alice_file("links_dir/sub/two.jpg")
    cid = _collection(client, alice, "Links dir")
    _add(client, alice, cid, "personal", "links_dir/one.jpg")
    _add(client, alice, cid, "personal", "links_dir/sub/two.jpg")
    _favorite(client, alice, "personal", "links_dir/sub/two.jpg")

    _restore(client, alice, _trash(client, alice, "personal", "links_dir"))
    assert _in_collection(client, alice, cid) == {"links_dir/one.jpg", "links_dir/sub/two.jpg"}
    assert "links_dir/sub/two.jpg" in _favorites(client, alice, "personal")


def test_links_follow_the_new_name_when_the_old_one_is_taken(client, alice):
    _alice_file("links_taken.jpg")
    cid = _collection(client, alice, "Links taken")
    _add(client, alice, cid, "personal", "links_taken.jpg")
    _favorite(client, alice, "personal", "links_taken.jpg")

    item = _trash(client, alice, "personal", "links_taken.jpg")
    _alice_file("links_taken.jpg")  # something else took the name
    path = _restore(client, alice, item)["path"]

    assert path == "links_taken (2).jpg"
    assert _in_collection(client, alice, cid) == {path}
    assert path in _favorites(client, alice, "personal")
    assert "links_taken.jpg" not in _favorites(client, alice, "personal")


def test_family_files_come_back_for_the_others_too(client, alice, bob):
    _family_file("links_family.jpg")
    cid = _collection(client, bob, "Bob's trip")
    _add(client, bob, cid, "family", "links_family.jpg")
    _favorite(client, bob, "family", "links_family.jpg")

    item = _trash(client, alice, "family", "links_family.jpg")
    assert _in_collection(client, bob, cid) == set()

    _restore(client, alice, item)
    assert _in_collection(client, bob, cid) == {"links_family.jpg"}
    assert "links_family.jpg" in _favorites(client, bob, "family")
    assert "links_family.jpg" not in _favorites(client, alice, "family")


def test_a_collection_deleted_meanwhile_stays_deleted(client, alice):
    _alice_file("links_gone.jpg")
    cid = _collection(client, alice, "Links gone")
    _add(client, alice, cid, "personal", "links_gone.jpg")
    item = _trash(client, alice, "personal", "links_gone.jpg")

    assert client.delete("/api/collections", headers=alice, params={"id": cid}).status_code == 200
    assert _restore(client, alice, item)["path"] == "links_gone.jpg"
    listed = [c["id"] for c in client.get("/api/collections", headers=alice).json()["collections"]]
    assert cid not in listed


def test_the_client_never_sees_who_pointed_at_a_file(client, alice, bob):
    _family_file("links_private.jpg")
    _favorite(client, bob, "family", "links_private.jpg")
    item = _trash(client, alice, "family", "links_private.jpg")

    # It is kept for the restore...
    info = json.loads((NAS / ".trash" / "alice1" / item / ".nas_trash.json").read_text())
    assert info["links"]["favorites"][0][0] == "bob1"
    # ...but neither the trash list nor the restore tell anyone about it.
    listed = client.get("/api/trash", headers=alice)
    assert "bob1" not in listed.text and "links" not in next(i for i in listed.json()["items"] if i["id"] == item)
    restored = client.post("/api/trash/restore", headers=alice, data={"id": item})
    assert "bob1" not in restored.text and set(restored.json()) == {"space", "path"}


def test_an_item_deleted_forever_does_not_come_back_in_collections(client, alice):
    _alice_file("links_forever.jpg")
    cid = _collection(client, alice, "Links forever")
    _add(client, alice, cid, "personal", "links_forever.jpg")
    item = _trash(client, alice, "personal", "links_forever.jpg")
    assert client.delete("/api/trash", headers=alice, params={"id": item}).status_code == 200
    assert _in_collection(client, alice, cid) == set()
