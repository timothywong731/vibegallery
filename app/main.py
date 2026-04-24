from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from .config import settings, IMAGE_EXTS
from .scanner import scan_gallery

app = FastAPI(title="Photo Gallery Web App")

app.mount("/images", StaticFiles(directory=settings.gallery_root), name="images")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the gallery web app")
    parser.add_argument("--host", default=os.getenv("GALLERY_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GALLERY_PORT", os.getenv("PORT", "8000"))),
    )
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


@app.get("/health")
async def health():
    return {"status": "ok"}


# No thumbnail cache or startup creation required — browser will handle rescaling.


@app.get("/", response_class=HTMLResponse)
async def index():
    # Redirect to slideshow as primary UI (no uploading in web version)
    return RedirectResponse(url='/slideshow')


# Uploads are not supported in the web app; users select local directories for slideshow.

# ---------------- Random Slideshow Functionality ----------------
from random import sample, shuffle
from fastapi import Query
from .scanner import iter_image_files
from .config import settings

def _resolve_dir(d: str | None) -> Path:
    if not d:
        return settings.gallery_root
    p = Path(d).expanduser().resolve()
    # Allow any existing directory on local filesystem; caller should ensure this is intended.
    if not p.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")
    return p

@app.get("/api/random")
async def api_random(
    directory: str | None = None,
    rows: int = Query(2, ge=1, le=10),
    cols: int = Query(2, ge=1, le=10),
    refresh: int = Query(5, ge=1, le=3600),
    limit_scan: int = Query(5000, ge=1, le=20000),
):
    root = _resolve_dir(directory)
    # Collect up to limit_scan images
    images = []
    for i, p in enumerate(iter_image_files(root)):
        images.append(p)
        if i + 1 >= limit_scan:
            break
    total = len(images)
    needed = rows * cols
    if total == 0:
        return {"images": [], "total": 0, "rows": rows, "cols": cols, "refresh": refresh}
    if total <= needed:
        chosen = images
        shuffle(chosen)
    else:
        chosen = sample(images, needed)
    # Return full paths as strings; client will request /serve?path=... and browser will resize
    return {"images": [str(p) for p in chosen], "total": total, "rows": rows, "cols": cols, "refresh": refresh, "directory": str(root)}

@app.get("/serve")


async def serve(path: str):
    # Basic path normalization
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    if p.suffix.lower() not in IMAGE_EXTS:
        raise HTTPException(status_code=400, detail="Unsupported extension")
    return FileResponse(p)


# Thumbnail generation removed: let the browser rescale images. If we later reintroduce
# server-side thumbnails we can re-add a safe, atomic generator.

@app.get("/slideshow", response_class=HTMLResponse)
async def slideshow(request: Request):
    return templates.TemplateResponse("slideshow.html", {"request": request, "settings": settings})


@app.get("/api/pick-directory")
async def pick_directory():
    """Open a native OS folder-picker dialog and return the chosen path."""
    import asyncio

    def _pick() -> str | None:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", True)
            path = filedialog.askdirectory(title="Select Image Directory")
            root.destroy()
            return path or None
        except Exception:
            return None

    path = await asyncio.to_thread(_pick)
    return {"path": path}


@app.delete("/api/image")
async def delete_image(path: str):
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    if p.suffix.lower() not in IMAGE_EXTS:
        raise HTTPException(status_code=400, detail="Not an image file")
    try:
        p.unlink()
        return {"deleted": str(p)}
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/raw/{path:path}")
async def raw_image(path: str):
    full = settings.gallery_root / path
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(full)


# Convenience root run entry
if __name__ == "__main__":
    main()
