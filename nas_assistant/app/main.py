import asyncio
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import disks, favorites, media, storage
from .auth import User, admin_user, current_user

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="NAS Assistant", version="0.9.0")

# Small boards: decode at most two big images at once. Waiting requests queue
# here, outside the worker threads, so uploads and browsing never stall behind them.
_thumb_slots = asyncio.Semaphore(2)


@app.get("/api/me")
async def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "display_name": user.display_name, "is_admin": user.is_admin}


@app.get("/api/status")
async def status(user: User = Depends(current_user)):
    state = disks.state()
    return {"disk": state, "usage": storage.usage() if state == "mounted" else None}


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


@app.get("/api/files")
async def list_files(space: str = "personal", path: str = "", user: User = Depends(current_user)):
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
    favorites.moved(user, space, path, space, os.path.join(os.path.dirname(path.strip("/")), result["name"]))
    return result


@app.post("/api/move")
async def move(request: Request, user: User = Depends(current_user)):
    space, path, to_space, to_path = await _fields(request, "space", "path", "to_space", "to_path", optional=("to_path",))
    result = await run_in_threadpool(storage.move, user, space, path, to_space, to_path)
    favorites.moved(user, space, path, to_space, result["path"])
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


@app.get("/api/photos")
def photos(space: str = "personal", user: User = Depends(current_user)):
    items = media.gallery(user, space)
    favs = favorites.paths(user, space)
    for item in items:
        item["fav"] = item["path"] in favs
    return {"space": space, "items": items}


@app.get("/api/thumb")
async def thumb(space: str, path: str, size: str = "s", user: User = Depends(current_user)):
    src = storage.resolve(user, space, path)
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


@app.get("/api/upload")
async def upload_status(space: str, name: str, path: str = "", user: User = Depends(current_user)):
    """How many bytes of an interrupted upload the server already has."""
    partial, _ = storage.chunk_targets(user, space, path, name)
    return {"offset": partial.stat().st_size if partial.exists() else 0}


@app.put("/api/upload")
async def upload_chunk(
    request: Request, space: str, name: str, path: str = "", offset: int = 0, final: bool = False,
    user: User = Depends(current_user),
):
    """Resumable upload, one chunk per request: send the file in pieces with
    their byte offset; the last piece has final=1. A 409 tells the client
    how much the server already has, so it can resume from there."""
    partial, target = storage.chunk_targets(user, space, path, name)
    have = partial.stat().st_size if partial.exists() else 0
    if offset and offset != have:
        raise HTTPException(409, {"message": "Resuming upload", "offset": have})
    with open(partial, "ab" if offset else "wb") as out:
        async for chunk in request.stream():
            out.write(chunk)
    if not final:
        return {"offset": partial.stat().st_size}
    os.replace(partial, target)
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
    target = storage.resolve(user, space, path)
    if not target.is_file():
        raise HTTPException(404, "File not found")
    # Supports HTTP Range requests, which Safari/iOS need to play videos.
    return FileResponse(target, filename=target.name,
                        content_disposition_type="inline" if inline else "attachment")


@app.delete("/api/files")
async def delete(space: str, path: str, user: User = Depends(current_user)):
    item_id = storage.move_to_trash(user, space, path)
    favorites.removed(user, space, path)
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


class WebFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = UI_CACHE
        return response


app.mount("/", WebFiles(directory=WEB_DIR, html=True), name="web")
