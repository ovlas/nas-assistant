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
from typing import Dict, Optional, Tuple

import aiohttp
from fastapi import HTTPException, Request

INGRESS_IP = "172.30.32.2"
HA_WS_URL = os.environ.get("NAS_HA_WS_URL", "ws://homeassistant:8123/api/websocket")
# Local development only: trust X-Remote-User-* headers from this IP too.
DEV_TRUSTED_IP = os.environ.get("NAS_DEV_TRUSTED_IP")
TOKEN_CACHE_SECONDS = 300


@dataclass(frozen=True)
class User:
    id: str
    name: str
    display_name: str


_token_cache: Dict[str, Tuple[float, User]] = {}


def _from_ingress(request: Request) -> Optional[User]:
    client_ip = request.client.host if request.client else None
    if client_ip not in (INGRESS_IP, DEV_TRUSTED_IP):
        return None
    user_id = request.headers.get("X-Remote-User-Id")
    if not user_id:
        return None
    name = request.headers.get("X-Remote-User-Name", "")
    display = request.headers.get("X-Remote-User-Display-Name") or name
    return User(id=user_id, name=name, display_name=display)


async def _from_bearer(token: str) -> Optional[User]:
    key = hashlib.sha256(token.encode()).hexdigest()
    cached = _token_cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(HA_WS_URL, timeout=10) as ws:
                await ws.receive_json()  # auth_required
                await ws.send_json({"type": "auth", "access_token": token})
                if (await ws.receive_json()).get("type") != "auth_ok":
                    return None
                await ws.send_json({"id": 1, "type": "auth/current_user"})
                result = (await ws.receive_json()).get("result") or {}
    except (aiohttp.ClientError, TimeoutError):
        raise HTTPException(503, "Home Assistant non raggiungibile")

    if not result.get("id"):
        return None
    user = User(id=result["id"], name=result.get("name", ""), display_name=result.get("name", ""))
    _token_cache[key] = (time.monotonic() + TOKEN_CACHE_SECONDS, user)
    return user


async def current_user(request: Request) -> User:
    user = _from_ingress(request)
    if user:
        return user
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        user = await _from_bearer(auth[len("Bearer "):])
        if user:
            return user
    raise HTTPException(401, "Accesso non autorizzato")
