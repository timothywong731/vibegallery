# Photo Gallery (Web Version)

A FastAPI-based web application that lets you upload and browse images in a simple responsive grid. This is a web adaptation of the original Tkinter desktop slideshow app.

## Features

- Upload images (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.webp`, `.tiff`)
- Auto-deduplicated file naming (adds numeric suffix if name exists)
- Lightweight gallery scanner (recursive under `images/` folder)
- Image metadata (dimensions + file size) extracted via Pillow
- Basic HTML/CSS (no JS required) using Jinja2 templates
- Health endpoint at `/health`
- Random slideshow page at `/slideshow` (choose directory, rows, cols, refresh interval)
- JSON random selection API at `/api/random`

## Project Layout

```
app/
  main.py          # FastAPI app + routes
  config.py        # Settings (paths, limits, extensions)
  scanner.py       # File system scanning + metadata extraction
  models.py        # Simple dataclass for image metadata
  templates/       # Jinja2 templates (base + index)
  static/          # Static assets placeholder
images/            # Created automatically; user uploads stored here
photoapp.py        # Original Tkinter application (unchanged)
```

## Requirements

- Python 3.13+ (per `pyproject.toml`)
- Dependencies managed by Poetry (or install manually with pip)

## Installation

Using Poetry (recommended):

```powershell
poetry install
```

Using `pip` directly:

```powershell
pip install -e .
```

(If installing without Poetry lock resolution you may also need to install: `pip install fastapi uvicorn[standard] jinja2 pillow python-multipart`)

## Running the Development Server

```powershell
poetry run uvicorn app.main:app --reload --port 8000
```

Or run the packaged entry point:

```powershell
poetry run gallery
```

If port 8000 is already in use, run on another port:

```powershell
poetry run gallery --port 8001
```

Then open: http://127.0.0.1:8000/

Slideshow interface: http://127.0.0.1:8000/slideshow

Note: The web app does not accept uploads. Instead, point the slideshow at any local directory (relative to server) containing images; the server will randomly select rows*cols images from that directory and refresh at the configured interval. Use the slider on the slideshow page to adjust refresh frequency.

## Running Tests

```powershell
poetry run pytest -q
```

## Configuration

Edit `app/config.py` to adjust:
- `gallery_root` (default: `images/`)
- `max_upload_size_mb` (default: 25MB)
- Allowed extensions list

## Notes vs Desktop Version

The desktop version supports multi-image slideshow grids, random shuffle, and animated GIF playback. The web version focuses on directory-driven random slideshow (no uploads). Potential future enhancements are listed below.

The new slideshow page mimics the random grid selection behavior: it fetches a random set of images (rows * cols) every N seconds without reloading the page.

## Roadmap / Possible Enhancements

- Pagination / infinite scroll for large galleries
- On-the-fly thumbnail generation & caching
- Slideshow mode with timed transitions
- Animated image frame extraction for preview (GIF/WebP)
- Sorting & filtering (date, size, name)
- Authentication / private galleries
- Drag & drop uploads & multi-file batching
- EXIF metadata display (orientation, camera model)
- Delete / rename operations
- Directory chooser UI (server-side browsing with safeguards)
- Improved security sandbox for arbitrary directory access
- Caching thumbnails / resizing variants

## License

MIT (adjust as desired)
