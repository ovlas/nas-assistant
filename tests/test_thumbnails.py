"""A picture that can't be decoded is a missing thumbnail, never a server error."""

import pytest

from conftest import NAS
from nas_assistant.app import media


@pytest.mark.parametrize("error", [ZeroDivisionError("bad EXIF"), ValueError("bad size"), OSError("truncated")])
def test_a_broken_picture_is_no_server_error(client, bob, monkeypatch, error):
    folder = NAS / "users" / "bob1"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"broken_{type(error).__name__}.jpg").write_bytes(b"x" * 100)

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(media.Image, "open", fail)
    r = client.get("/api/thumb", headers=bob, params={"space": "personal", "path": f"broken_{type(error).__name__}.jpg"})
    assert r.status_code == 415
