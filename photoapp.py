#!/usr/bin/env python3
"""
Random Photo Gallery — v4 (Lazy Scan, Rows×Cols Grid, 0.5s steps)

Key changes (compared to v3):
- **No preloading of entire folder**: non-blocking, lazy background scan using a worker thread.
- UI remains responsive; images appear as they are discovered.
- Grid is controlled by **Rows** × **Cols**; photos per slide = rows*cols.
- Duration supports **0.5 s** increments (0.5–30.0 s).
- Play/Pause, Next/Prev, Shuffle, Reshuffle.

Requirements
- Python 3.8+
- Pillow (PIL):  pip install pillow

Run
    python photo_gallery_v4.py
    python photo_gallery_v4.py /path/to/photos
"""
from __future__ import annotations

import os
import random
import sys
import threading
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover
    raise SystemExit("Pillow is required. Install with: pip install pillow")

from queue import Queue, Empty

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}


class PhotoGalleryApp:
    def __init__(self, root: tk.Tk, start_dir: Optional[Path] = None) -> None:
        self.root = root
        self.root.title("Random Photo Gallery — v4 (lazy scan)")
        self.root.geometry("1200x800")
        self.root.minsize(720, 540)

        # Files & ordering (grow over time)
        self.folder: Optional[Path] = start_dir
        self.files: List[Path] = []        # Indexed image paths (grows lazily)
        self.order: List[int] = []         # Playback order (indices into files)
        self.idx: int = 0                  # Start index of current slide in order

        # Playback state
        self.is_playing: bool = False
        self.after_id: Optional[str] = None
        self.current_photos: List[ImageTk.PhotoImage] = []

        # Lazy scanner state
        self._scan_thread: Optional[threading.Thread] = None
        self._scan_queue: Optional[Queue] = None
        self._scan_stop = threading.Event()
        self._scanning: bool = False
        self._indexed_count: int = 0

        # Tk variables
        self.duration_var = tk.DoubleVar(value=5.0)
        self.shuffle_var = tk.BooleanVar(value=True)
        self.rows_var = tk.IntVar(value=2)
        self.cols_var = tk.IntVar(value=2)

        # UI
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<space>", self._toggle_play_pause)
        self.root.bind("<Left>", lambda e: self.prev_image())
        self.root.bind("<Right>", lambda e: self.next_image())
        self.root.bind("<Configure>", self._on_resize)

        if self.folder and self.folder.exists():
            self._start_scan(self.folder)

    # ---------------------------- UI ----------------------------
    def _build_ui(self) -> None:
        # Top bar
        top = ttk.Frame(self.root, padding=(10, 10, 10, 0))
        top.pack(fill=tk.X)
        self.folder_label = ttk.Label(top, text="No folder selected", anchor="w")
        self.folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(top, text="Choose Folder", command=self.choose_folder).pack(side=tk.RIGHT)

        # Canvas
        self.canvas = tk.Canvas(self.root, bg="#111111", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Controls
        controls = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        controls.pack(fill=tk.X)

        self.play_btn = ttk.Button(controls, text="▶ Play", command=self.start_slideshow)
        self.pause_btn = ttk.Button(controls, text="⏸ Pause", command=self.pause_slideshow, state=tk.DISABLED)
        self.play_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(controls, text="⟵ Prev", command=self.prev_image).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Next ⟶", command=self.next_image).pack(side=tk.LEFT, padx=(0, 12))

        # Duration (0.5–30.0)
        ttk.Label(controls, text="Duration (s):").pack(side=tk.LEFT)
        self.duration_scale = ttk.Scale(controls, from_=0.5, to=30.0, orient=tk.HORIZONTAL, command=self._on_duration_change)
        self.duration_scale.set(self.duration_var.get())
        self.duration_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        self.duration_spin = ttk.Spinbox(controls, from_=0.5, to=30.0, increment=0.5, width=6,
                                         textvariable=self.duration_var, command=self._sync_duration_from_spin, format="%.1f")
        self.duration_spin.pack(side=tk.LEFT, padx=(0, 12))

        # Rows / Cols (1–8)
        ttk.Label(controls, text="Rows:").pack(side=tk.LEFT)
        self.rows_spin = ttk.Spinbox(controls, from_=1, to=8, width=3, textvariable=self.rows_var, command=self._on_grid_change)
        self.rows_spin.pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(controls, text="Cols:").pack(side=tk.LEFT)
        self.cols_spin = ttk.Spinbox(controls, from_=1, to=8, width=3, textvariable=self.cols_var, command=self._on_grid_change)
        self.cols_spin.pack(side=tk.LEFT, padx=(6, 12))

        # Shuffle & reshuffle
        ttk.Checkbutton(controls, text="Shuffle", variable=self.shuffle_var, command=self._maybe_shuffle).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Reshuffle Now", command=self._reshuffle_keep_current).pack(side=tk.LEFT)

        # Status
        self.status = ttk.Label(self.root, text="Tip: Choose a folder to begin. Space=Play/Pause • ←/→ Prev/Next", anchor="w")
        self.status.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Optional ttk theme (ignored if missing)
        try:
            self.root.call("source", "sun-valley.tcl")
            self.root.call("set_theme", "dark")
        except tk.TclError:
            pass

    # ------------------------- Folder / Scan -------------------------
    def choose_folder(self) -> None:
        path = filedialog.askdirectory(title="Choose a folder with images")
        if not path:
            return
        self._start_scan(Path(path))

    def _start_scan(self, folder: Path) -> None:
        # Stop any previous scan
        self._stop_scan_thread()

        # Reset state
        self.folder = folder
        self.files.clear()
        self.order.clear()
        self.idx = 0
        self._indexed_count = 0
        self.folder_label.config(text=str(folder))
        self.status.config(text="Scanning… 0 files indexed")
        self.canvas.delete("all")

        # Start new scan thread
        self._scan_queue = Queue(maxsize=512)
        self._scan_stop.clear()
        self._scanning = True
        self._scan_thread = threading.Thread(target=self._scan_images_thread, args=(folder,), daemon=True)
        self._scan_thread.start()
        # Poll queue from Tk thread
        self.root.after(60, self._poll_scan_queue)

    def _stop_scan_thread(self) -> None:
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_stop.set()
            self._scan_thread.join(timeout=0.5)
        self._scan_thread = None
        self._scan_stop.clear()
        self._scanning = False

    def _scan_images_thread(self, folder: Path) -> None:
        """Walk the folder lazily and push paths to the queue."""
        try:
            for root, _dirs, files in os.walk(folder):
                if self._scan_stop.is_set():
                    break
                for name in files:
                    if self._scan_stop.is_set():
                        break
                    if Path(name).suffix.lower() in IMAGE_EXTS:
                        p = Path(root, name)
                        try:
                            self._scan_queue.put(p, timeout=0.5)
                        except Exception:
                            if self._scan_stop.is_set():
                                break
                            # if queue is full and UI is slow, keep trying
                            try:
                                self._scan_queue.put(p, timeout=1.0)
                            except Exception:
                                if self._scan_stop.is_set():
                                    break
            # Signal completion
            try:
                self._scan_queue.put(None, timeout=0.2)
            except Exception:
                pass
        except Exception:
            # Best-effort completion signal on unexpected errors
            try:
                self._scan_queue.put(None, timeout=0.2)
            except Exception:
                pass

    def _poll_scan_queue(self) -> None:
        if not self._scan_queue:
            return
        updated = False
        try:
            while True:
                item = self._scan_queue.get_nowait()
                if item is None:
                    self._scanning = False
                    break
                # Append and integrate into order
                new_idx = len(self.files)
                self.files.append(item)
                self._indexed_count += 1
                if self.shuffle_var.get():
                    # Insert at a random position after current slide to avoid immediate jump
                    insert_pos = random.randint(self.idx, len(self.order)) if self.order else 0
                    self.order.insert(insert_pos, new_idx)
                else:
                    self.order.append(new_idx)
                updated = True
        except Empty:
            pass

        if updated:
            if self._indexed_count == 1:
                # First image ready — show it immediately
                self.show_current()
            status_extra = " (done)" if not self._scanning else ""
            self.status.config(text=f"Scanning… {self._indexed_count} files indexed{status_extra}")

        # Keep polling while scanning or while there are still items being drained
        if self._scanning or (self._scan_queue and not self._scan_queue.empty()):
            self.root.after(100, self._poll_scan_queue)
        else:
            # Final update
            self.status.config(text=f"Indexed {self._indexed_count} files from: {self.folder}")

    # ----------------------- Playback & Timing -----------------------
    def start_slideshow(self) -> None:
        if not self.files:
            messagebox.showinfo("Select a folder", "Please choose a folder with images first.")
            return
        self.is_playing = True
        self.play_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.status.config(text="Playing…")
        self._schedule_next()

    def pause_slideshow(self) -> None:
        self.is_playing = False
        self.play_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.status.config(text="Paused")
        self._cancel_after()

    def _schedule_next(self) -> None:
        self._cancel_after()
        if not self.is_playing:
            return
        delay_ms = max(0.5, float(self.duration_var.get())) * 1000
        self.after_id = self.root.after(int(delay_ms), self.next_image)

    def _cancel_after(self) -> None:
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _on_duration_change(self, _val: str) -> None:
        try:
            val = float(_val)
        except ValueError:
            return
        snapped = round(val * 2) / 2.0
        self.duration_var.set(snapped)
        if self.is_playing:
            self._schedule_next()

    def _sync_duration_from_spin(self) -> None:
        try:
            val = float(self.duration_var.get())
        except (tk.TclError, ValueError):
            val = 1.0
        val = min(30.0, max(0.5, val))
        snapped = round(val * 2) / 2.0
        self.duration_var.set(snapped)
        self.duration_scale.set(snapped)
        if self.is_playing:
            self._schedule_next()

    def _on_grid_change(self) -> None:
        rows = self._bounded_int(self.rows_var.get(), 1, 8)
        cols = self._bounded_int(self.cols_var.get(), 1, 8)
        self.rows_var.set(rows)
        self.cols_var.set(cols)
        pps = max(1, rows * cols)
        if pps > 0:
            self.idx = (self.idx // pps) * pps
        self.show_current()
        if self.is_playing:
            self._schedule_next()

    @staticmethod
    def _bounded_int(value, lo: int, hi: int) -> int:
        try:
            v = int(value)
        except (ValueError, tk.TclError):
            v = lo
        return max(lo, min(hi, v))

    def _toggle_play_pause(self, _event=None) -> None:
        if self.is_playing:
            self.pause_slideshow()
        else:
            self.start_slideshow()

    # --------------------------- Navigation ---------------------------
    def _pps(self) -> int:
        return max(1, int(self.rows_var.get()) * int(self.cols_var.get()))

    def next_image(self) -> None:
        if not self.files:
            return
        pps = self._pps()
        self.idx += pps
        if self.idx >= len(self.order):
            # Wrap; if shuffle and scanning is done, reshuffle for freshness
            self.idx = 0
            if self.shuffle_var.get() and not self._scanning and self.order:
                random.shuffle(self.order)
        self.show_current()
        if self.is_playing:
            self._schedule_next()

    def prev_image(self) -> None:
        if not self.files:
            return
        pps = self._pps()
        self.idx -= pps
        if self.idx < 0:
            # Wrap to last full slide boundary
            n = len(self.order)
            if n == 0:
                return
            remainder = n % pps
            last_boundary = n - (remainder if remainder != 0 else pps)
            self.idx = max(0, last_boundary)
        self.show_current()
        if self.is_playing:
            self._schedule_next()

    # -------------------------- Rendering --------------------------
    def _on_resize(self, _event=None) -> None:
        if self.files:
            self.show_current()

    def _current_indices(self) -> List[int]:
        if not self.order:
            return []
        pps = self._pps()
        start = self.idx
        end = min(len(self.order), start + pps)
        if start >= len(self.order):
            start = max(0, len(self.order) - pps)
            end = len(self.order)
        return self.order[start:end]

    def show_current(self) -> None:
        if not self.order:
            self.canvas.delete("all")
            return
        indices = self._current_indices()
        k = len(indices)
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        pad = 8

        rows = max(1, int(self.rows_var.get()))
        cols = max(1, int(self.cols_var.get()))
        cell_w = (cw - pad * (cols + 1)) // cols
        cell_h = (ch - pad * (rows + 1)) // rows
        cell_w = max(1, cell_w)
        cell_h = max(1, cell_h)

        self.current_photos = []
        self.canvas.delete("all")

        for i, file_idx in enumerate(indices):
            path = self.files[file_idx]
            try:
                img = Image.open(path)
            except Exception as e:
                self.status.config(text=f"Failed to open {path.name}: {e}")
                continue

            img_ratio = img.width / img.height
            cell_ratio = cell_w / cell_h
            if img_ratio > cell_ratio:
                new_w = cell_w
                new_h = int(cell_w / img_ratio)
            else:
                new_h = cell_h
                new_w = int(cell_h * img_ratio)
            try:
                img = img.resize((max(1, new_w), max(1, new_h)), Image.LANCZOS)
            except Exception:
                img = img.resize((max(1, new_w), max(1, new_h)))

            photo = ImageTk.PhotoImage(img)
            self.current_photos.append(photo)

            r = i // cols
            c = i % cols
            x0 = pad + c * (cell_w + pad)
            y0 = pad + r * (cell_h + pad)
            x = x0 + (cell_w - new_w) // 2
            y = y0 + (cell_h - new_h) // 2
            self.canvas.create_rectangle(x0, y0, x0 + cell_w, y0 + cell_h, outline="#333333")
            self.canvas.create_image(x, y, anchor=tk.NW, image=photo)

            name = path.name
            if len(name) > 40:
                name = name[:37] + "…"
            self.canvas.create_text(x0 + 6, y0 + cell_h - 6, anchor=tk.SW, text=name, fill="#dddddd")

        # Status footer
        pps = self._pps()
        slide_num = (self.idx // pps) + 1 if pps else 1
        total_slides = (len(self.order) + pps - 1) // pps if pps else 1
        scanning_txt = " • Scanning…" if self._scanning else ""
        self.canvas.create_text(
            8, ch - 8, anchor=tk.SW,
            text=f"Slide {min(slide_num, max(1,total_slides))}/{max(1,total_slides)} • Grid {rows}×{cols} • Showing {k} of {len(self.files)} files{scanning_txt}",
            fill="#cccccc"
        )

    # --------------------------- Shuffle ---------------------------
    def _maybe_shuffle(self) -> None:
        if self.shuffle_var.get() and self.order:
            self._reshuffle_keep_current()

    def _reshuffle_keep_current(self) -> None:
        if not self.order:
            return
        current_set = self._current_indices()
        random.shuffle(self.order)
        if current_set:
            try:
                # Keep the first item of the current slide at the same position
                pos = self.order.index(current_set[0])
                anchor = self.idx if self.idx < len(self.order) else 0
                self.order[pos], self.order[anchor] = self.order[anchor], self.order[pos]
            except ValueError:
                pass
        self.show_current()

    # --------------------------- Cleanup ---------------------------
    def _on_close(self) -> None:
        self._cancel_after()
        self._stop_scan_thread()
        self.root.destroy()


def main() -> None:
    start_dir = None
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser()
        if p.exists() and p.is_dir():
            start_dir = p
    root = tk.Tk()
    PhotoGalleryApp(root, start_dir=start_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
