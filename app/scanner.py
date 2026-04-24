from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from .config import settings, IMAGE_EXTS
from .models import ImageMeta

from PIL import Image


def iter_image_files(root: Path) -> Iterable[Path]:
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            p = Path(dirpath) / name
            if p.suffix.lower() in IMAGE_EXTS:
                yield p


def scan_gallery(limit: int | None = None) -> List[ImageMeta]:
    images: List[ImageMeta] = []
    count = 0
    root = settings.gallery_root
    for p in iter_image_files(root):
        rel = p.relative_to(root).as_posix()
        try:
            size = p.stat().st_size
        except OSError:
            continue
        width = height = None
        try:
            with Image.open(p) as im:
                width, height = im.size
        except Exception:
            pass
        images.append(ImageMeta(path=p, rel_path=rel, size=size, width=width, height=height))
        count += 1
        if limit and count >= limit:
            break
    return images
