"""Uploads in pieces that can arrive in any order, over several connections at once.

A big file is cut in pieces (a few MB each); the browser sends three or four of them at
the same time. Each piece says where it goes in the file, and is written exactly there in
the hidden ".name.part" file; ".name.part.ranges" notes which stretches have arrived. When
they cover the whole file, and only then, it gets its real name.

So a frozen or cut connection only delays its own piece, the others keep going; a piece
cut half way keeps what arrived; a piece sent twice writes the same bytes again (harmless);
and after a reload the browser asks which stretches are missing and sends only those.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List

from fastapi.concurrency import run_in_threadpool

Ranges = List[List[int]]
_locks: Dict[str, asyncio.Lock] = {}


def _ranges_file(partial: Path) -> Path:
    return partial.with_name(partial.name + ".ranges")


def load(partial: Path) -> Ranges:
    """The stretches of the file already received, merged and sorted."""
    try:
        return json.loads(_ranges_file(partial).read_text())
    except (OSError, ValueError):
        # An upload started piece after piece, in order (older pages, the mobile app).
        size = partial.stat().st_size if partial.exists() else 0
        return [[0, size]] if size else []


def _save(partial: Path, ranges: Ranges) -> None:
    tmp = _ranges_file(partial).with_suffix(".tmp")
    tmp.write_text(json.dumps(ranges))
    os.replace(tmp, _ranges_file(partial))


def add(ranges: Ranges, start: int, end: int) -> Ranges:
    if end <= start:
        return ranges
    merged: Ranges = []
    for a, b in sorted(ranges + [[start, end]]):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def complete(ranges: Ranges, size: int) -> bool:
    return size == 0 or (len(ranges) == 1 and ranges[0][0] == 0 and ranges[0][1] >= size)


def forget(partial: Path) -> None:
    try:
        _ranges_file(partial).unlink()
    except FileNotFoundError:
        pass


async def begin(partial: Path) -> None:
    """Before the first piece is written: note what is already there. A ".part" without
    a ranges file grew in order (older pages, the mobile app), so its size is one stretch;
    once pieces are written at any position, its size says nothing any more."""
    lock = _locks.setdefault(str(partial), asyncio.Lock())
    async with lock:
        if not _ranges_file(partial).exists():
            await run_in_threadpool(_save, partial, load(partial))


async def receive(stream, partial: Path, offset: int, size: int) -> int:
    """Write the incoming bytes of one piece at `offset`. Returns where it stopped: also
    when the connection drops half way, everything that arrived is on disk."""
    fd = await run_in_threadpool(os.open, str(partial), os.O_RDWR | os.O_CREAT, 0o644)
    position = offset
    buffer = bytearray()
    try:
        async for chunk in stream:
            buffer += chunk
            if len(buffer) >= 4 * 1024 * 1024:
                position += await run_in_threadpool(os.pwrite, fd, bytes(buffer[:size - position]), position)
                buffer.clear()
    finally:
        if buffer and position < size:
            position += await run_in_threadpool(os.pwrite, fd, bytes(buffer[:size - position]), position)
        await run_in_threadpool(os.close, fd)
    return position


async def note(partial: Path, target: Path, start: int, end: int, size: int) -> bool:
    """Record a received stretch; when the file is whole, give it its name. True when done."""
    lock = _locks.setdefault(str(partial), asyncio.Lock())
    async with lock:
        if not partial.exists():  # another piece already finished the file
            return target.exists() and target.stat().st_size == size
        ranges = add(load(partial), start, end)
        if not complete(ranges, size):
            await run_in_threadpool(_save, partial, ranges)
            return False
        await run_in_threadpool(os.truncate, partial, size)
        await run_in_threadpool(os.replace, partial, target)
        forget(partial)
        _locks.pop(str(partial), None)
        return True
