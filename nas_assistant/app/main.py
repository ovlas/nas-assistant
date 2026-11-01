from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import disks, storage
from .auth import User, admin_user, current_user

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="NAS Assistant", version="0.2.0")


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


@app.post("/api/disks/use")
def use_disk(uuid: str = Form(...), user: User = Depends(admin_user)):
    disks.use_partition(uuid)
    return {"ok": True}


@app.post("/api/disks/format")
def format_disk(path: str = Form(...), confirm: str = Form(...), user: User = Depends(admin_user)):
    disks.format_disk(path, confirm)
    return {"ok": True}


@app.get("/api/files")
async def list_files(space: str = "personal", path: str = "", user: User = Depends(current_user)):
    return {"space": space, "path": path, "entries": storage.list_dir(user, space, path)}


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


@app.get("/api/download")
async def download(space: str, path: str, user: User = Depends(current_user)):
    target = storage.resolve(user, space, path)
    if not target.is_file():
        raise HTTPException(404, "File non trovato")
    return FileResponse(target, filename=target.name)


@app.delete("/api/files")
async def delete(space: str, path: str, user: User = Depends(current_user)):
    storage.move_to_trash(user, space, path)
    return {"ok": True}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
