"""The gallery: Photos shows photos and videos, Videos only the videos."""

from conftest import NAS


def test_gallery_can_show_only_the_videos(client, bob):
    home = NAS / "users" / "bob1" / "Galleria"
    home.mkdir(parents=True, exist_ok=True)
    (home / "mare.mp4").write_bytes(b"x" * 100)
    (home / "festa.mov").write_bytes(b"x" * 100)
    (home / "cane.jpg").write_bytes(b"x" * 100)

    everything = client.get("/api/photos", headers=bob, params={"space": "personal", "limit": 300}).json()
    videos = client.get("/api/photos", headers=bob, params={"space": "personal", "limit": 300, "kind": "video"}).json()

    assert {"mare.mp4", "festa.mov", "cane.jpg"} <= {i["name"] for i in everything["items"]}
    assert {i["kind"] for i in videos["items"]} == {"video"}
    assert {"mare.mp4", "festa.mov"} <= {i["name"] for i in videos["items"]}
    # The counts follow the filter: pages and months add up to the videos alone.
    assert videos["total"] == videos["videos"] == everything["videos"]
    assert videos["images"] == 0
    assert sum(videos["months"].values()) == videos["total"]

    # Pages are cut after the filter, so none comes back short.
    page = client.get("/api/photos", headers=bob,
                      params={"space": "personal", "limit": 1, "offset": 1, "kind": "video"}).json()
    assert [i["path"] for i in page["items"]] == [videos["items"][1]["path"]]
