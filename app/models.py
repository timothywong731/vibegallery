from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class ImageMeta:
    path: Path
    rel_path: str
    size: int
    width: Optional[int] = None
    height: Optional[int] = None

