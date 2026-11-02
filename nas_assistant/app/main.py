import asyncio
import errno
import io
import os
import secrets
import shutil
import tempfile
import time
from typing import Dict
from pathlib import Path

import aiohttp
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from urllib.parse import urlencode

from . import albums, backup, devices, diskadmin, disks, favorites, media, plugplay, rawdisk, storage, tv
from .auth import User, admin_user, avatar, current_user
from .kinds import media_kind

import segno

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="NAS Assistant", version="0.21.1")

# Small boards: decode at most two big images at once. Waiting requests queue
# here, outside the worker threads, so uploads and browsing never stall behind them.
_thumb_slots = asyncio.Semaphore(2)


@app.on_event("startup")
async def start_backup_scheduler():
    asyncio.get_running_loop().create_task(backup.scheduler())


@app.on_event("startup")
async def warm_folders():
    # Big disks: read every folder once now, so the first pages don't wait for it.
    asyncio.get_running_loop().run_in_executor(None, storage.warm)


@app.on_event("startup")
async def start_disk_watch():
    asyncio.get_running_loop().create_task(plugplay.watch())


@app.on_event("startup")
async def find_home_address():
    """The IP address of Home Assistant on the home network, from the Supervisor."""
    global LAN_IP_URL
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return
    try:
        async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {token}"},
                                         timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("http://supervisor/network/info") as resp:
                interfaces = (await resp.json()).get("data", {}).get("interfaces", [])
        for iface in sorted(interfaces, key=lambda i: not i.get("primary")):
            for address in (iface.get("ipv4") or {}).get("address") or []:
                LAN_IP_URL = f"http://{address.split('/')[0]}:8456"
                return
    except (aiohttp.ClientError, TimeoutError, ValueError):
        pass


@app.on_event("startup")
def keep_temp_files_on_nas_disk():
    """Uploads are buffered in temp files: keep them on the NAS disk, not on Home Assistant's."""
    if disks.state() == "mounted":
        tmp = disks.NAS_ROOT / ".nas_assistant" / "tmp"
        shutil.rmtree(tmp, ignore_errors=True)  # leftovers of an interrupted upload
        tmp.mkdir(parents=True, exist_ok=True)
        tempfile.tempdir = str(tmp)


# --- Devices: uploads from a phone in the background (iOS Shortcuts) ----------

PUBLIC_URL = os.environ.get("NAS_PUBLIC_URL", "").rstrip("/")
LAN_URL = "http://homeassistant.local:8456"
LAN_IP_URL = ""  # e.g. http://192.168.1.10:8456, found at startup: Android can't resolve .local names
PHOTO_FOLDERS = {"it": "Foto", "es": "Fotos", "de": "Fotos", "fr": "Photos"}
UPLOAD_FOLDERS = {"it": "Caricati", "es": "Subidas", "de": "Hochgeladen", "fr": "Importés"}


async def uploader(request: Request) -> User:
    """A device key (upload only) or a normal Home Assistant login."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer " + devices.PREFIX):
        user = await run_in_threadpool(devices.owner, auth[len("Bearer "):])
        if not user:
            raise HTTPException(401, "Not authorized")
        return user
    return await current_user(request)


@app.get("/api/devices")
def list_devices(user: User = Depends(current_user)):
    return {"devices": devices.listing(user), "public_url": PUBLIC_URL, "lan_url": LAN_URL}


def _base_urls() -> dict:
    return {"public": PUBLIC_URL, "lan": LAN_URL, "lan_ip": LAN_IP_URL}


@app.post("/api/devices/pairing")
async def start_pairing(user: User = Depends(current_user)):
    """A one-time QR code (10 minutes) for the mobile app to pair this phone."""
    pairing = devices.start_pairing(user)
    # A web address, so a phone camera without the app opens a page that explains what to do.
    # The code is after "#": browsers never send that part to the server or to Cloudflare.
    params = urlencode({"v": 1, "code": pairing["code"], "url": PUBLIC_URL, "lan": LAN_URL, "ip": LAN_IP_URL})
    text = f"{PUBLIC_URL or LAN_URL}/pair#{params}"
    svg = io.BytesIO()
    segno.make(text, error="m").save(svg, kind="svg", scale=6, border=2, dark="#0b1f4d", xmldecl=False, svgns=True)
    return {**pairing, "qr": text, "qr_svg": svg.getvalue().decode(), "started": int(time.time())}


@app.get("/api/devices/paired")
def paired(since: int, user: User = Depends(current_user)):
    return {"paired": devices.is_paired(user, since)}


@app.post("/api/device/pair")
async def pair_device(request: Request):
    """Called by the app with the code read from the QR: no login, the code is the proof."""
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(422, "Required fields: code")
    if not isinstance(body, dict) or not isinstance(body.get("code"), str):
        raise HTTPException(422, "Required fields: code")
    client = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else "")
    result = await run_in_threadpool(devices.pair, body["code"], str(body.get("name", ""))[:60],
                                     str(body.get("platform", ""))[:20], client)
    return {**result, "urls": _base_urls()}


@app.delete("/api/device")
def disconnect_self(user: User = Depends(uploader)):
    """The app's "Disconnect": a device removes its own key."""
    if not user.device_id:
        raise HTTPException(400, "Only a device can disconnect itself")
    devices.revoke(user, user.device_id)
    return {"ok": True}


@app.get("/api/device/info")
def device_info(user: User = Depends(uploader)):
    return {"user": {"display_name": user.display_name}, "device": {"name": user.device},
            "usage": storage.usage(), "version": app.version}


@app.post("/api/devices")
async def add_device(request: Request, user: User = Depends(current_user)):
    (name,) = await _fields(request, "name")
    key = await run_in_threadpool(devices.create, user, name)
    return {"key": key, "public_url": PUBLIC_URL, "lan_url": LAN_URL}


@app.delete("/api/devices")
def remove_device(id: str, user: User = Depends(current_user)):
    devices.revoke(user, id)
    return {"ok": True}


def _incoming() -> Path:
    folder = disks.NAS_ROOT / ".nas_assistant" / "incoming"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _store_from_device(user: User, upload: UploadFile, space: str, lang: str) -> dict:
    name = os.path.basename(upload.filename or "") or f"file-{int(time.time())}"
    tmp = _incoming() / secrets.token_hex(8)
    with open(tmp, "wb") as out:
        shutil.copyfileobj(upload.file, out, 4 * 1024 * 1024)
    return _place(user, tmp, name, space, lang)


def _place(user: User, tmp: Path, name: str, space: str, lang: str) -> dict:
    """Move a received file into the user's space: photos and videos by capture date."""
    try:
        kind = media_kind(name)
        if kind:
            # Photos and videos go to Photos/<year>/<month> of when they were taken, like the camera roll.
            taken = time.localtime(media._taken(tmp, kind, time.time()))
            folder = f"{PHOTO_FOLDERS.get(lang, 'Photos')}/{taken.tm_year}/{taken.tm_mon:02d}"
        else:
            folder = UPLOAD_FOLDERS.get(lang, "Uploads")
        target_dir = storage.resolve(user, space, folder)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / storage._check_name(name)
        size = tmp.stat().st_size
        # Shortcuts may send the same photo again: skip what is already there.
        if target.exists() and target.stat().st_size == size:
            return {"path": storage.to_rel(user, space, target), "skipped": True}
        target = storage._free_name(target_dir, target.name)
        os.replace(tmp, target)
        return {"path": storage.to_rel(user, space, target), "size": size, "skipped": False}
    finally:
        tmp.unlink(missing_ok=True)


@app.post("/api/device/upload")
async def device_upload(request: Request, file: UploadFile = File(...), space: str = Form("personal"),
                        user: User = Depends(uploader)):
    """One file per request, multipart field "file": what an iOS Shortcut's
    "Get contents of URL" sends. Folders are chosen by the server."""
    lang = request.headers.get("Accept-Language", "en")[:2].lower()
    return await run_in_threadpool(_store_from_device, user, file, space, lang)


def _device_partial(user: User, name: str) -> Path:
    """Where a chunked device upload grows: one hidden file per user and name."""
    name = storage._check_name(os.path.basename(name))
    # One folder per device: two phones of the same person may send files with the same name.
    folder = _incoming() / user.id / (user.device_id or "web")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f".{name}.part"


@app.get("/api/device/upload")
def device_upload_status(name: str, user: User = Depends(uploader)):
    partial = _device_partial(user, name)
    return {"offset": partial.stat().st_size if partial.exists() else 0}


@app.put("/api/device/upload")
async def device_upload_chunk(request: Request, name: str, offset: int = 0, final: bool = False,
                              space: str = "personal", user: User = Depends(uploader)):
    """Resumable upload for big files (videos), 16 MB pieces, same protocol as /api/upload;
    the last piece (final=1) places the file like POST /api/device/upload."""
    partial = _device_partial(user, name)
    have = partial.stat().st_size if partial.exists() else 0
    if offset and offset != have:
        raise HTTPException(409, {"message": "Resuming upload", "offset": have})
    with open(partial, "ab" if offset else "wb") as out:
        async for chunk in request.stream():
            out.write(chunk)
    if not final:
        return {"offset": partial.stat().st_size}
    lang = request.headers.get("Accept-Language", "en")[:2].lower()
    return await run_in_threadpool(_place, user, partial, os.path.basename(name), space, lang)


@app.get("/api/backup")
async def backup_status(user: User = Depends(current_user)):
    return await run_in_threadpool(backup.status)


@app.post("/api/backup/run")
async def backup_now(user: User = Depends(admin_user)):
    if not await backup.start():
        raise HTTPException(409, "A backup is already running")
    return {"ok": True}


@app.get("/api/avatar")
async def user_avatar(user: User = Depends(current_user)):
    """The user's picture from their Home Assistant person, if they have one."""
    picture = await avatar(user.id)
    if not picture:
        raise HTTPException(404, "Not found")
    return Response(picture[0], media_type=picture[1], headers={"Cache-Control": "private, max-age=600"})


@app.exception_handler(OSError)
async def disk_errors(request: Request, err: OSError):
    """A full NAS disk is the most likely write error: say so plainly (507 Insufficient Storage)."""
    if err.errno == errno.ENOSPC:
        return JSONResponse({"detail": "NAS disk is full"}, status_code=507)
    raise err


@app.get("/api/me")
async def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "display_name": user.display_name, "is_admin": user.is_admin}


@app.get("/api/status")
async def status(user: User = Depends(current_user)):
    state = disks.state()
    result = {"disk": state, "usage": storage.usage() if state == "mounted" else None}
    if user.is_admin:
        result["new_disks"] = list(plugplay.new_disks.values())  # plugged in, waiting for a choice
    return result


@app.get("/api/disks")
def list_disks(user: User = Depends(admin_user)):
    return {"disks": disks.list_disks()}


async def _fields(request: Request, *names: str, optional: tuple = ()) -> list:
    """Read fields from a form (web UI) or a JSON body (mobile apps).
    Fields listed in `optional` may be empty, e.g. the root folder path."""
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
    else:
        data = await request.form()
    values = [data.get(name, "" if name in optional else None) for name in names]
    if not all(isinstance(v, str) and (v or n in optional) for n, v in zip(names, values)):
        raise HTTPException(422, f"Required fields: {', '.join(names)}")
    return values


@app.get("/api/disks/overview")
def disks_overview(user: User = Depends(admin_user)):
    return {"disks": diskadmin.overview(), "nas": disks.state(),
            "roles": {role: {"state": state, "fstype": fstype} for role, (_, _, state, fstype) in diskadmin.ROLES.items()},
            "storage_name": storage.EXTRA_NAME, "away": plugplay.away()}


# --- Watch on the TV ------------------------------------------------------------

@app.get("/api/tv/players")
async def tv_players(user: User = Depends(current_user)):
    return {"players": await tv.players(), "ready": bool(LAN_IP_URL)}


@app.post("/api/tv/play")
async def tv_play(request: Request, user: User = Depends(current_user)):
    """Play one file, or a slideshow (items in order), on a TV known to Home Assistant."""
    data = await request.json()
    entity_id, items = data.get("entity_id"), data.get("items")
    if not (isinstance(entity_id, str) and entity_id.startswith("media_player.") and isinstance(items, list) and items
            and all(isinstance(i, dict) and isinstance(i.get("space"), str) and isinstance(i.get("path"), str)
                    for i in items)):
        raise HTTPException(422, "Required fields: entity_id, items")
    if not LAN_IP_URL:
        raise HTTPException(503, "Home network address unknown: restart NAS Assistant")
    files = [_source(user, i["space"], i["path"]) for i in items[:2000]]
    await tv.play(entity_id, LAN_IP_URL, [f for f in files if f.is_file()])
    return {"ok": True, "slideshow": len(files) > 1}


@app.post("/api/tv/stop")
async def tv_stop(request: Request, user: User = Depends(current_user)):
    (entity_id,) = await _fields(request, "entity_id")
    await tv.stop(entity_id)
    return {"ok": True}


@app.api_route("/tv/{token}/{name}", methods=["GET", "HEAD"])
async def tv_file(token: str, name: str, request: Request):
    """The file a TV asked for: only from the home network, with a link made for it."""
    if not tv.from_home(request):
        raise HTTPException(404, "Not found")
    src = tv.target(token)
    if media.kind_of(src.name) == "image":
        out = await run_in_threadpool(tv.tv_photo, src)
        return FileResponse(out, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    return FileResponse(src, media_type=tv._content_type(src), headers={"Cache-Control": "no-store"})


@app.get("/api/disk/roots")
def disk_roots(user: User = Depends(admin_user)):
    """The disks whose other files can be browsed."""
    return {"disks": [{"space": rawdisk.PREFIX + key, "role": key} for key in rawdisk.mounts()]}


@app.post("/api/disk/copy")
async def disk_copy(request: Request, user: User = Depends(admin_user)):
    """Copy a file or folder of the disk into My space or Family (in the background)."""
    space, path, to_space, to_path = await _fields(request, "space", "path", "to_space", "to_path", optional=("to_path",))
    return await run_in_threadpool(rawdisk.start_copy, user, space, path, to_space, to_path)


@app.get("/api/disk/jobs")
def disk_jobs(user: User = Depends(admin_user)):
    return {"jobs": rawdisk.user_jobs(user)}


@app.post("/api/disks/role")
async def set_disk_role(request: Request, user: User = Depends(admin_user)):
    """role: backup, storage or none. The add-on restarts to apply it; nothing is erased."""
    device_id, role = await _fields(request, "id", "role")
    await diskadmin.set_role(device_id, None if role == "none" else role)
    plugplay.forget_new(device_id)
    return {"ok": True, "restarting": True}


@app.post("/api/disks/dismiss")
async def dismiss_new_disk(request: Request, user: User = Depends(admin_user)):
    """"Not now" on the new-disk banner."""
    (device_id,) = await _fields(request, "id")
    plugplay.forget_new(device_id)
    return {"ok": True}


@app.post("/api/disks/eject")
async def eject_disk(request: Request, user: User = Depends(admin_user)):
    """Safely eject a disk: role nas (pauses the NAS), backup or storage."""
    (role,) = await _fields(request, "role")
    await diskadmin.eject(role)
    return {"ok": True}


@app.post("/api/disks/reactivate")
async def reactivate_nas(user: User = Depends(admin_user)):
    """The NAS disk is plugged back in after an eject: restart to mount it."""
    await diskadmin.reactivate()
    return {"ok": True, "restarting": True}


@app.post("/api/disks/initialize")
async def initialize_disk(request: Request, user: User = Depends(admin_user)):
    """Erase the backup or storage disk and make it ext4, only when its filesystem can't be used."""
    role, confirm = await _fields(request, "role", "confirm")
    await diskadmin.initialize(role, confirm)
    return {"ok": True, "restarting": True}


@app.post("/api/disks/use")
async def use_disk(request: Request, user: User = Depends(admin_user)):
    (uuid,) = await _fields(request, "uuid")
    await run_in_threadpool(disks.use_partition, uuid)
    return {"ok": True}


@app.post("/api/disks/format")
async def format_disk(request: Request, user: User = Depends(admin_user)):
    path, confirm = await _fields(request, "path", "confirm")
    await run_in_threadpool(disks.format_disk, path, confirm)
    return {"ok": True}


def _source(user: User, space: str, path: str):
    """A file of a space, or (administrators) of "Other files on the disk"."""
    if space.startswith(rawdisk.PREFIX):
        if not user.is_admin:
            raise HTTPException(403, "Only administrators can do this")
        return rawdisk.resolve(space, path)
    return storage.resolve(user, space, path)


@app.get("/api/files")
async def list_files(space: str = "personal", path: str = "", user: User = Depends(current_user)):
    if space.startswith(rawdisk.PREFIX):
        _source(user, space, "")
        return {"space": space, "path": path, "entries": await run_in_threadpool(rawdisk.list_dir, space, path)}
    entries = storage.list_dir(user, space, path)
    favs = favorites.paths(user, space)
    for entry in entries:
        entry["fav"] = os.path.normpath(os.path.join(path.strip("/"), entry["name"])) in favs
    return {"space": space, "path": path, "entries": entries}


@app.get("/api/files/by-kind")
def files_by_kind(space: str, kind: str, user: User = Depends(current_user)):
    entries = storage.files_by_kind(user, space, kind)
    favs = favorites.paths(user, space)
    for entry in entries:
        entry["fav"] = entry["path"] in favs
    return {"space": space, "kind": kind, "entries": entries}


@app.get("/api/favorites")
def list_favorites(space: str = "personal", user: User = Depends(current_user)):
    return {"space": space, "entries": favorites.listing(user, space)}


@app.post("/api/favorites")
async def set_favorite(request: Request, user: User = Depends(current_user)):
    """Body: space, path, favorite ("1" to add, "0" to remove)."""
    space, path, on = await _fields(request, "space", "path", "favorite")
    favorites.set_favorite(user, space, path, on in ("1", "true"))
    return {"ok": True}


@app.post("/api/rename")
async def rename(request: Request, user: User = Depends(current_user)):
    space, path, name = await _fields(request, "space", "path", "name")
    result = storage.rename(user, space, path, name)
    new_path = os.path.join(os.path.dirname(path.strip("/")), result["name"])
    favorites.moved(user, space, path, space, new_path)
    albums.moved(user, space, path, space, new_path)
    return result


@app.post("/api/move")
async def move(request: Request, user: User = Depends(current_user)):
    space, path, to_space, to_path = await _fields(request, "space", "path", "to_space", "to_path", optional=("to_path",))
    result = await run_in_threadpool(storage.move, user, space, path, to_space, to_path)
    favorites.moved(user, space, path, to_space, result["path"])
    albums.moved(user, space, path, to_space, result["path"])
    return result


@app.get("/api/home")
def home(user: User = Depends(current_user)):
    """Everything the welcome page shows, in one request."""
    photos = media.gallery(user, "personal")
    favs = favorites.paths(user, "personal")
    for item in photos[:8]:
        item["fav"] = item["path"] in favs
    images = sum(1 for p in photos if p["kind"] == "image")
    return {
        "photos": {"images": images, "videos": len(photos) - images, "recent": photos[:8]},
        # Photos and videos have their own card.
        "recent": storage.recent_files(user, "personal", 8, skip_kinds=("image", "video")),
        "family": storage.recent_files(user, "family", 5),
        "favorites": favorites.listing(user, "personal")[:6],
        "trash": storage.trash_count(user),
    }


# --- Collections: albums and dossiers -------------------------------------------

@app.get("/api/collections")
def list_collections(user: User = Depends(current_user)):
    return {"collections": albums.listing(user)}


@app.post("/api/collections")
async def create_collection(request: Request, user: User = Depends(current_user)):
    """Body: name, kind (album or dossier), shared ("1" for the whole family)."""
    name, kind, shared = await _fields(request, "name", "kind", "shared", optional=("shared",))
    return albums.create(user, name, kind, shared in ("1", "true"))


@app.post("/api/collections/rename")
async def rename_collection(request: Request, user: User = Depends(current_user)):
    collection_id, name = await _fields(request, "id", "name")
    albums.rename(user, collection_id, name)
    return {"ok": True}


@app.delete("/api/collections")
def delete_collection(id: str, user: User = Depends(current_user)):
    albums.delete(user, id)
    return {"ok": True}


@app.get("/api/collections/items")
def collection_items(id: str, user: User = Depends(current_user)):
    data = albums.items(user, id)
    favs = {space: favorites.paths(user, space) for space in storage.SPACES}
    for item in data["items"]:
        item["fav"] = item["path"] in favs[item["space"]]
    return data


@app.post("/api/collections/items")
async def add_to_collection(request: Request, user: User = Depends(current_user)):
    collection_id, space, path = await _fields(request, "id", "space", "path")
    albums.add(user, collection_id, space, path)
    return {"ok": True}


@app.delete("/api/collections/items")
def remove_from_collection(id: str, space: str, path: str, user: User = Depends(current_user)):
    albums.remove(user, id, space, path)
    return {"ok": True}


@app.get("/api/photos")
def photos(space: str = "personal", user: User = Depends(current_user)):
    items = media.gallery(user, space)
    favs = favorites.paths(user, space)
    for item in items:
        item["fav"] = item["path"] in favs
    return {"space": space, "items": items}


@app.get("/api/thumb")
async def thumb(space: str, path: str, size: str = "s", user: User = Depends(current_user)):
    src = _source(user, space, path)
    out = media.thumb_path(src, size)
    if not out.exists():
        async with _thumb_slots:
            await run_in_threadpool(media.make_thumbnail, src, size, out)
    # The URL carries the file version (?v=mtime), so the browser may cache it forever.
    return FileResponse(out, media_type="image/webp",
                        headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.post("/api/folders")
async def create_folder(
    space: str = Form(...), path: str = Form(""), name: str = Form(...),
    user: User = Depends(current_user),
):
    storage.make_dir(user, space, path, name)
    return {"ok": True}


@app.post("/api/upload")
def upload(
    space: str = Form(...), path: str = Form(""), file: UploadFile = File(...),
    user: User = Depends(current_user),
):
    # Sync handler: FastAPI runs it in a thread, so big copies don't block the event loop.
    return storage.save_file(user, space, path, file.filename or "file", file.file)


# --- Uploads straight to the add-on ------------------------------------------------
#
# Through Home Assistant's Ingress an upload crawls (measured: minutes for 20 MB), while the
# add-on's own port takes 60 MB/s on the home network, and the public address (Cloudflare)
# a few MB/s from outside. The page asks for an upload pass (12 hours, this user, uploads
# only) and sends the pieces straight there; with no direct way it keeps using Ingress.

UPLOAD_PASS_PREFIX = "upl_"
UPLOAD_PASS_SECONDS = 12 * 3600
_upload_passes: Dict[str, tuple] = {}  # pass -> (user, expires)
UPLOAD_PATHS = ("/api/upload", "/api/upload/ping")


@app.middleware("http")
async def upload_cors(request: Request, call_next):
    """Let the page (served through Home Assistant) send uploads to the add-on's own address.
    Only the upload endpoints, and only with an upload pass: no cookies are involved."""
    if request.url.path not in UPLOAD_PATHS:
        return await call_next(request)
    headers = {"Access-Control-Allow-Origin": request.headers.get("origin", "*"),
               "Access-Control-Allow-Methods": "GET, PUT",
               "Access-Control-Allow-Headers": "Authorization, Content-Type",
               "Access-Control-Allow-Private-Network": "true",
               "Access-Control-Max-Age": "600", "Vary": "Origin"}
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=headers)
    response = await call_next(request)
    response.headers.update(headers)
    return response


async def web_uploader(request: Request) -> User:
    """An upload pass (direct uploads) or the normal Home Assistant login (Ingress)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer " + UPLOAD_PASS_PREFIX):
        entry = _upload_passes.get(auth[len("Bearer "):])
        if not entry or entry[1] < time.time():
            raise HTTPException(401, "Not authorized")
        return entry[0]
    return await current_user(request)


@app.post("/api/upload/session")
def upload_session(user: User = Depends(current_user)):
    now = time.time()
    for key in [k for k, (_, expires) in _upload_passes.items() if expires < now]:
        del _upload_passes[key]
    token = UPLOAD_PASS_PREFIX + secrets.token_urlsafe(24)
    _upload_passes[token] = (user, now + UPLOAD_PASS_SECONDS)
    return {"token": token, "lan": LAN_IP_URL, "public": PUBLIC_URL}


@app.get("/api/upload/ping")
def upload_ping():
    return {"ok": True}


@app.get("/api/upload")
async def upload_status(space: str, name: str, path: str = "", size: int = -1, user: User = Depends(web_uploader)):
    """How many bytes of an interrupted upload the server already has. With `size`, the
    whole plan: already there (skip), resume, or the name to use if it is taken."""
    if size >= 0:
        return await run_in_threadpool(storage.upload_plan, user, space, path, name, size)
    partial, _ = storage.chunk_targets(user, space, path, name)
    return {"offset": partial.stat().st_size if partial.exists() else 0}


@app.put("/api/upload")
async def upload_chunk(
    request: Request, space: str, name: str, path: str = "", offset: int = 0, final: bool = False,
    user: User = Depends(web_uploader),
):
    """Resumable upload, one chunk per request: send the file in pieces with
    their byte offset; the last piece has final=1. A 409 tells the client
    how much the server already has, so it can resume from there."""
    partial, target = storage.chunk_targets(user, space, path, name)
    have = partial.stat().st_size if partial.exists() else 0
    if offset and offset != have:
        raise HTTPException(409, {"message": "Resuming upload", "offset": have})
    # The disk may be slow (USB 2, NTFS): write in a worker thread, in big blocks, so other
    # requests (and the other pieces) never wait behind it.
    out = await run_in_threadpool(open, partial, "ab" if offset else "wb")
    try:
        buffer = bytearray()
        async for chunk in request.stream():
            buffer += chunk
            if len(buffer) >= 4 * 1024 * 1024:
                await run_in_threadpool(out.write, bytes(buffer))
                buffer.clear()
        if buffer:
            await run_in_threadpool(out.write, bytes(buffer))
    finally:
        await run_in_threadpool(out.close)
    if not final:
        return {"offset": partial.stat().st_size}
    await run_in_threadpool(os.replace, partial, target)
    return {"name": target.name, "size": target.stat().st_size}


@app.get("/api/trash")
def trash(user: User = Depends(current_user)):
    return {"items": storage.list_trash(user), "days": storage.TRASH_DAYS}


@app.get("/api/trash/thumb")
async def trash_thumb(id: str, size: str = "s", user: User = Depends(current_user)):
    src = storage.trash_file(user, id)
    out = media.thumb_path(src, size)
    if not out.exists():
        async with _thumb_slots:
            await run_in_threadpool(media.make_thumbnail, src, size, out)
    return FileResponse(out, media_type="image/webp",
                        headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.post("/api/trash/restore")
async def restore(request: Request, user: User = Depends(current_user)):
    (item_id,) = await _fields(request, "id")
    return await run_in_threadpool(storage.restore, user, item_id)


@app.delete("/api/trash")
def delete_forever(id: str = "", all: bool = False, user: User = Depends(current_user)):
    """Delete one item for good, or empty the whole trash with all=1."""
    if all:
        storage.empty_trash(user)
    elif id:
        storage.delete_forever(user, id)
    else:
        raise HTTPException(422, "Required fields: id")
    return {"ok": True}


@app.get("/api/download")
async def download(space: str, path: str, inline: bool = False, user: User = Depends(current_user)):
    target = _source(user, space, path)
    if not target.is_file():
        raise HTTPException(404, "File not found")
    # Supports HTTP Range requests, which Safari/iOS need to play videos.
    return FileResponse(target, filename=target.name,
                        content_disposition_type="inline" if inline else "attachment")


@app.delete("/api/files")
async def delete(space: str, path: str, user: User = Depends(current_user)):
    item_id = storage.move_to_trash(user, space, path)
    favorites.removed(user, space, path)
    albums.removed(user, space, path)
    return {"id": item_id}


# The web UI must never be kept by proxies such as Cloudflare (which otherwise
# caches .js/.css for hours) and browsers must check for a new version on every
# load. On top of that, index.html links the files with ?v=<version>, so an
# update always means new URLs.
UI_CACHE = "private, no-cache"
INDEX_HTML = (WEB_DIR / "index.html").read_text().replace("{{version}}", app.version)


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
async def index():
    return HTMLResponse(INDEX_HTML, headers={"Cache-Control": UI_CACHE})


@app.get("/pair", include_in_schema=False)
async def pair_page():
    """Opened by a phone camera that scans the pairing QR without the app installed."""
    return FileResponse(WEB_DIR / "pair.html", headers={"Cache-Control": UI_CACHE})


class WebFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = UI_CACHE
        return response


app.mount("/", WebFiles(directory=WEB_DIR, html=True), name="web")
