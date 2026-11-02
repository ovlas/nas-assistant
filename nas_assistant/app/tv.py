"""Watch on the TV: play photos and videos on a TV, through Home Assistant.

Home Assistant already knows the TVs and speakers of the house (Chromecast, Google TV,
Samsung, LG, Apple TV…) as media_player entities. NAS Assistant asks it to play a link;
the TV then fetches the file straight from the add-on on the home network.

Each link is a random secret that works for a few hours and only from the home network:
requests coming through a tunnel (Cloudflare) are refused, so a link can't leak outside.
Photos are sent as JPEG (TVs don't read HEIC), videos as they are.
"""

import asyncio
import ipaddress
import logging
import mimetypes
import os
import secrets
import time
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
from fastapi import HTTPException, Request
from PIL import Image, ImageOps

from . import media
from .kinds import media_kind

log = logging.getLogger("uvicorn.error")

LINK_SECONDS = 4 * 3600
PHOTO_SECONDS = 7  # each photo of a slideshow
_links: Dict[str, tuple] = {}  # token -> (file, expires)
_shows: Dict[str, asyncio.Task] = {}  # entity_id -> running slideshow
SUPERVISOR = "http://supervisor/core/api"


async def _ha(method: str, path: str, body: Optional[dict] = None):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise HTTPException(503, "Home Assistant is not reachable")
    async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {token}"},
                                     timeout=aiohttp.ClientTimeout(total=20)) as session:
        async with session.request(method, SUPERVISOR + path, json=body) as resp:
            if resp.status >= 300:
                raise HTTPException(502, "Home Assistant refused the request")
            return await resp.json(content_type=None)


async def players() -> List[dict]:
    """The media players of the house that are on or can be turned on."""
    states = await _ha("GET", "/states")
    found = []
    for item in states:
        entity_id = item.get("entity_id", "")
        if not entity_id.startswith("media_player.") or item.get("state") in ("unavailable", "unknown"):
            continue
        attrs = item.get("attributes") or {}
        found.append({"id": entity_id, "name": attrs.get("friendly_name") or entity_id,
                      "state": item.get("state"), "playing": entity_id in _shows})
    return sorted(found, key=lambda p: (p["state"] == "off", p["name"].lower()))


def link(base_url: str, src: Path) -> str:
    """A secret, temporary link to one file, for the TV."""
    now = time.time()
    for token in [t for t, (_, expires) in _links.items() if expires < now]:
        del _links[token]
    token = secrets.token_urlsafe(18)
    _links[token] = (src, now + LINK_SECONDS)
    name = "photo.jpg" if media_kind(src.name) == "image" else src.name
    return f"{base_url}/tv/{token}/{name}"


def from_home(request: Request) -> bool:
    """True for a device of the home network talking to the add-on directly (not through a tunnel)."""
    if any(h in request.headers for h in ("cf-connecting-ip", "x-forwarded-for", "cf-ray")):
        return False
    try:
        return ipaddress.ip_address(request.client.host).is_private
    except (AttributeError, ValueError):
        return False


def target(token: str) -> Path:
    entry = _links.get(token)
    if not entry or entry[1] < time.time() or not entry[0].is_file():
        raise HTTPException(404, "Not found")
    return entry[0]


def tv_photo(src: Path) -> Path:
    """The photo as a Full HD JPEG, upright: what every TV can show. Cached."""
    out = media.thumb_path(src, "l").with_suffix(".tv.jpg")
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        img = ImageOps.exif_transpose(Image.open(src))
        img.thumbnail((1920, 1920))
        partial = out.with_suffix(f".{os.getpid()}.part")
        img.convert("RGB").save(partial, "JPEG", quality=88)
        os.replace(partial, out)
    except (OSError, SyntaxError):
        raise HTTPException(415, "Can't read the photo")
    return out


def _content_type(src: Path) -> str:
    if media_kind(src.name) == "image":
        return "image/jpeg"
    if src.suffix.lower() in (".mov", ".m4v"):
        return "video/mp4"  # QuickTime from an iPhone: TVs play it when told it's MP4
    return mimetypes.guess_type(src.name)[0] or "video/mp4"


async def _play(entity_id: str, url: str, src: Path) -> None:
    await _ha("POST", "/services/media_player/play_media", {
        "entity_id": entity_id,
        "media_content_id": url,
        "media_content_type": _content_type(src),
        "extra": {"title": src.name},
    })


async def play(entity_id: str, base_url: str, files: List[Path], seconds: int = PHOTO_SECONDS) -> None:
    """Play one file, or a slideshow of many (photos for a few seconds, videos to the end)."""
    await stop(entity_id, quiet=True)
    if not files:
        raise HTTPException(400, "Nothing to show")
    await _play(entity_id, link(base_url, files[0]), files[0])
    if len(files) > 1:
        _shows[entity_id] = asyncio.get_running_loop().create_task(_slideshow(entity_id, base_url, files, seconds))


async def _wait_video(entity_id: str) -> None:
    """Until the TV has finished the video (or after 3 hours at most)."""
    started = False
    for _ in range(3 * 3600 // 2):
        await asyncio.sleep(2)
        try:
            state = (await _ha("GET", f"/states/{entity_id}")).get("state")
        except HTTPException:
            continue
        if state in ("playing", "buffering", "paused"):
            started = True
        elif started or state in ("off", "unavailable"):
            return


async def _slideshow(entity_id: str, base_url: str, files: List[Path], seconds: int) -> None:
    try:
        for index, src in enumerate(files):
            if index:
                await _play(entity_id, link(base_url, src), src)
            if media_kind(src.name) == "video":
                await _wait_video(entity_id)
            else:
                await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        raise
    except Exception as err:  # the TV went away: stop quietly
        log.info("Slideshow on %s stopped: %s", entity_id, err)
    finally:
        if _shows.get(entity_id) is asyncio.current_task():
            del _shows[entity_id]


async def stop(entity_id: str, quiet: bool = False) -> None:
    task = _shows.pop(entity_id, None)
    if task:
        task.cancel()
    if not quiet:
        try:
            await _ha("POST", "/services/media_player/media_stop", {"entity_id": entity_id})
        except HTTPException:
            pass
