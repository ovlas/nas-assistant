"""Identify the Home Assistant user behind a request.

Two ways in:
- Ingress (web UI in the HA sidebar): the Supervisor adds X-Remote-User-* headers.
  They are trusted only when the request comes from the Ingress proxy IP.
- Mobile apps: `Authorization: Bearer <HA access token>`, verified by asking
  Home Assistant who owns the token (websocket `auth/current_user`).
"""

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple

import aiohttp
from fastapi import Depends, HTTPException, Request

INGRESS_IP = "172.30.32.2"
HA_WS_URL = os.environ.get("NAS_HA_WS_URL", "ws://homeassistant:8123/api/websocket")
SUPERVISOR_WS_URL = "ws://supervisor/core/websocket"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
# Local development only: trust X-Remote-User-* headers from this IP too,
# and treat these user ids as admins.
DEV_TRUSTED_IP = os.environ.get("NAS_DEV_TRUSTED_IP")
DEV_ADMINS = frozenset(filter(None, os.environ.get("NAS_DEV_ADMINS", "").split(",")))
TOKEN_CACHE_SECONDS = 300
ADMIN_CACHE_SECONDS = 60


@dataclass(frozen=True)
class User:
    id: str
    name: str
    display_name: str
    is_admin: bool = False
    device: str = ""  # set when the request comes with a device key: its name…
    device_id: str = ""  # …and its id


_token_cache: Dict[str, Tuple[float, User]] = {}
_admin_cache: Tuple[float, FrozenSet[str]] = (0.0, frozenset())


async def _ws_call(url: str, token: str, message: dict) -> Optional[object]:
    """Authenticate on a HA websocket and return the result of one command."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url, timeout=10) as ws:
                await ws.receive_json()  # auth_required
                await ws.send_json({"type": "auth", "access_token": token})
                if (await ws.receive_json()).get("type") != "auth_ok":
                    return None
                await ws.send_json({"id": 1, **message})
                return (await ws.receive_json()).get("result")
    except (aiohttp.ClientError, TimeoutError):
        raise HTTPException(503, "Home Assistant is not reachable")


_avatar_cache: Dict[str, Tuple[float, Optional[Tuple[bytes, str]]]] = {}


async def avatar(user_id: str) -> Optional[Tuple[bytes, str]]:
    """The picture of the Home Assistant person linked to this user, as (bytes, content type)."""
    cached = _avatar_cache.get(user_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    picture = None
    if SUPERVISOR_TOKEN:
        headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get("http://supervisor/core/api/states") as resp:
                    states = await resp.json() if resp.status == 200 else []
                url = next((s["attributes"].get("entity_picture") for s in states
                            if s["entity_id"].startswith("person.")
                            and s["attributes"].get("user_id") == user_id
                            and s["attributes"].get("entity_picture")), None)
                # Only pictures served by Home Assistant itself, never an outside URL.
                if url and url.startswith("/"):
                    async with session.get(f"http://supervisor/core{url}") as resp:
                        if resp.status == 200:
                            picture = (await resp.read(), resp.content_type or "image/jpeg")
        except (aiohttp.ClientError, TimeoutError, ValueError, KeyError):
            picture = None
    _avatar_cache[user_id] = (time.monotonic() + 600, picture)
    return picture


async def _admin_ids() -> FrozenSet[str]:
    global _admin_cache
    if _admin_cache[0] > time.monotonic():
        return _admin_cache[1]
    users = await _ws_call(SUPERVISOR_WS_URL, SUPERVISOR_TOKEN, {"type": "config/auth/list"}) or []
    admins = frozenset(u["id"] for u in users if "system-admin" in (u.get("group_ids") or []))
    _admin_cache = (time.monotonic() + ADMIN_CACHE_SECONDS, admins)
    return admins


async def _from_ingress(request: Request) -> Optional[User]:
    client_ip = request.client.host if request.client else None
    if client_ip not in (INGRESS_IP, DEV_TRUSTED_IP):
        return None
    user_id = request.headers.get("X-Remote-User-Id")
    if not user_id:
        return None
    name = request.headers.get("X-Remote-User-Name", "")
    display = request.headers.get("X-Remote-User-Display-Name") or name
    if DEV_TRUSTED_IP and client_ip == DEV_TRUSTED_IP:
        is_admin = user_id in DEV_ADMINS
    else:
        is_admin = user_id in await _admin_ids()
    return User(id=user_id, name=name, display_name=display, is_admin=is_admin)


async def _from_bearer(token: str) -> Optional[User]:
    key = hashlib.sha256(token.encode()).hexdigest()
    cached = _token_cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    result = await _ws_call(HA_WS_URL, token, {"type": "auth/current_user"}) or {}
    if not result.get("id"):
        return None
    user = User(id=result["id"], name=result.get("name", ""), display_name=result.get("name", ""),
                is_admin=bool(result.get("is_admin")))
    _token_cache[key] = (time.monotonic() + TOKEN_CACHE_SECONDS, user)
    return user


async def current_user(request: Request) -> User:
    user = await _from_ingress(request)
    if user:
        return user
    auth = request.headers.get("Authorization", "")
    # Device keys (nas_…) and upload passes (upl_…) only work for uploads; never sent to Home Assistant.
    if auth.startswith("Bearer ") and not auth.startswith(("Bearer nas_", "Bearer upl_")):
        client = _client_id(request)
        _check_failures(client)
        user = await _from_bearer(auth[len("Bearer "):])
        if user:
            return user
        _failed(client)
    raise HTTPException(401, "Not authorized")


# Wrong tokens are checked against Home Assistant: a flood of them could guess nothing
# (tokens are long) but would load Home Assistant and fill its log. A few per minute per address.
MAX_FAILED_TOKENS = 10
_token_failures: Dict[str, Tuple[float, int]] = {}


def _client_id(request: Request) -> str:
    # Through a tunnel every request comes from the tunnel: tell its visitors apart.
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "")


def _check_failures(client: str) -> None:
    start, count = _token_failures.get(client, (0.0, 0))
    if count >= MAX_FAILED_TOKENS and time.monotonic() - start < 60:
        raise HTTPException(429, "Too many attempts, try again in a minute")


def _failed(client: str) -> None:
    now = time.monotonic()
    start, count = _token_failures.get(client, (now, 0))
    if now - start > 60:
        start, count = now, 0
    _token_failures[client] = (start, count + 1)
    if len(_token_failures) > 10000:  # don't grow without end
        _token_failures.clear()


async def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "A Home Assistant administrator is required")
    return user
