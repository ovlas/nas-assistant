import asyncio
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import disks, media, storage
from .auth import User, admin_user, current_user

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="NAS Assistant", version="0.5.0")

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
    return {"space": space, "path": path, "entries": storage.list_dir(user, space, path)}


@app.get("/api/files/by-kind")
def files_by_kind(space: str, kind: str, user: User = Depends(current_user)):
    return {"space": space, "kind": kind, "entries": storage.files_by_kind(user, space, kind)}


@app.post("/api/rename")
async def rename(request: Request, user: User = Depends(current_user)):
    space, path, name = await _fields(request, "space", "path", "name")
    return storage.rename(user, space, path, name)


@app.post("/api/move")
async def move(request: Request, user: User = Depends(current_user)):
    space, path, to_space, to_path = await _fields(request, "space", "path", "to_space", "to_path", optional=("to_path",))
    return await run_in_threadpool(storage.move, user, space, path, to_space, to_path)


@app.get("/api/photos")
def photos(space: str = "personal", user: User = Depends(current_user)):
    return {"space": space, "items": media.gallery(user, space)}


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
    storage.move_to_trash(user, space, path)
    return {"ok": True}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
