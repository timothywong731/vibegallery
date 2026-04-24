from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import os

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}

class Settings:
    def __init__(self) -> None:
        env_root = os.getenv("GALLERY_ROOT")
        self.gallery_root: Path = (
            Path(env_root).expanduser().resolve() if env_root else Path("images").absolute()
        )
        self.gallery_root.mkdir(parents=True, exist_ok=True)
        # Allow override via env var (e.g., set GALLERY_MAX_UPLOAD_MB=100)
        env_val: Optional[str] = os.getenv("GALLERY_MAX_UPLOAD_MB")
        try:
            self.max_upload_size_mb: int = int(env_val) if env_val else 100
        except ValueError:
            self.max_upload_size_mb = 100
        self.allowed_exts: List[str] = sorted(IMAGE_EXTS)
        # Thumbnail settings
        self.thumbnail_size = (420, 280)  # width, height in px
        env_cache = os.getenv("GALLERY_CACHE")
        cache_root = Path(env_cache).resolve() if env_cache else Path(".cache")
        self.thumbnail_cache = cache_root / "thumbnails"
        self.thumbnail_cache.mkdir(parents=True, exist_ok=True)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

settings = Settings()
