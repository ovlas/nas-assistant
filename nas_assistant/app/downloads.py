"""Downloads that don't crawl: a secret link to the add-on's own address.

Through Home Assistant's Ingress big downloads crawl and break, like uploads did. The page
asks for a link to one file or folder; the link works straight on the add-on (home
network, or the public address), for a few hours, for that item only. Files support
HTTP ranges, so a browser can resume a broken download; a folder comes as a .zip made
while it is sent (nothing is written to the disk first; files are stored, not compressed:
photos and videos are compressed already, and it stays fast).
"""

import os
import secrets
import time
import zipfile
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from fastapi import HTTPException

LINK_SECONDS = 6 * 3600
# token -> (the file, or the folder on each disk where it is; expires; download name)
_links: Dict[str, Tuple[List[Path], float, str]] = {}


def make(targets: List[Path]) -> dict:
    now = time.time()
    for token in [t for t, (_, expires, _) in _links.items() if expires < now]:
        del _links[token]
    targets = [t for t in targets if t.exists()]
    if not targets:
        raise HTTPException(404, "File not found")
    folder = targets[0].is_dir()
    token = secrets.token_urlsafe(24)
    name = targets[0].name + (".zip" if folder else "")
    _links[token] = (targets if folder else targets[:1], now + LINK_SECONDS, name)
    return {"token": token, "name": name, "folder": folder}


def get(token: str) -> Tuple[List[Path], str]:
    entry = _links.get(token)
    if not entry or entry[1] < time.time() or not any(t.exists() for t in entry[0]):
        raise HTTPException(404, "Not found")
    return [t for t in entry[0] if t.exists()], entry[2]


def _visible(name: str) -> bool:
    return not name.startswith((".", "$")) and name not in ("System Volume Information", "lost+found")


def folder_files(folders: List[Path]) -> List[Tuple[Path, str]]:
    """(file, name inside the zip) for every visible file of a folder; when the same folder is
    on two disks (the pool), both halves go in, a name present twice only once."""
    seen, found = set(), []
    for folder in folders:
        for top, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if _visible(d) and not os.path.islink(os.path.join(top, d)))
            for name in sorted(files):
                full = Path(top) / name
                arcname = os.path.join(folders[0].name, os.path.relpath(full, folder))
                if _visible(name) and not full.is_symlink() and arcname not in seen:
                    seen.add(arcname)
                    found.append((full, arcname))
    return found


class _Sink:
    """Where zipfile writes: bytes are handed to the response as they come."""

    def __init__(self):
        self.parts: List[bytes] = []

    def write(self, data) -> int:
        self.parts.append(bytes(data))
        return len(data)

    def flush(self) -> None:
        pass

    def take(self) -> bytes:
        data, self.parts = b"".join(self.parts), []
        return data


def zip_stream(files: List[Tuple[Path, str]]) -> Iterator[bytes]:
    sink = _Sink()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for full, arcname in files:
            try:  # a file that vanished or can't be read is left out; the rest still comes
                info = zipfile.ZipInfo.from_file(full, arcname)
                source = open(full, "rb")
            except OSError:
                continue
            with source, archive.open(info, "w", force_zip64=True) as out:
                while chunk := source.read(1024 * 1024):
                    out.write(chunk)
                    yield sink.take()
            yield sink.take()
    yield sink.take()
