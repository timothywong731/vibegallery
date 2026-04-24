from __future__ import annotations

from pathlib import Path
import shutil
import io
import sys

# Ensure project root is on sys.path so tests can import local `app` package when run in venv
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)

def setup_function(_func):
    # Ensure clean image directory
    if settings.gallery_root.exists():
        shutil.rmtree(settings.gallery_root)
    settings.gallery_root.mkdir(parents=True, exist_ok=True)


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_empty_gallery():
    r = client.get('/')
    # Index now redirects to slideshow; follow redirect or return slideshow HTML
    assert r.status_code in (200, 302, 307)
    if r.status_code == 200:
        assert b'Random Slideshow' in r.content


def test_upload_image():
    fake_png = (b'\x89PNG\r\n\x1a\n'  # PNG signature
                b'\x00\x00\x00\rIHDR'  # IHDR chunk
                b'\x00\x00\x00\x01\x00\x00\x00\x01'  # 1x1 image
                b'\x08\x06\x00\x00\x00'  # bit depth, color type, etc.
                b'\x1f\x15\xc4\x89'
                b'\x00\x00\x00\x0bIDAT'  # IDAT chunk
                b'\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe'  # compressed data
                b'\x00\x00\x00\x00IEND\xaeB`\x82')

    # This app no longer accepts uploads; ensure homepage redirects
    r = client.get('/')
    assert r.status_code in (200, 307, 302)


def test_random_api_empty(tmp_path, monkeypatch):
    # Point gallery root to temp path
    from app import config
    monkeypatch.setattr(config.settings, 'gallery_root', tmp_path)
    r = client.get('/api/random?rows=1&cols=2')
    assert r.status_code == 200
    data = r.json()
    assert data['images'] == []

def test_random_api_with_images(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, 'gallery_root', tmp_path)
    # Create 5 tiny PNG files
    png = (b'\x89PNG\r\n\x1a\n' b'\x00\x00\x00\rIHDR' b'\x00\x00\x00\x01\x00\x00\x00\x01' b'\x08\x06\x00\x00\x00' b'\x1f\x15\xc4\x89' b'\x00\x00\x00\x0bIDAT' b'\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe' b'\x00\x00\x00\x00IEND\xaeB`\x82')
    for i in range(5):
        (tmp_path / f'im{i}.png').write_bytes(png)
    r = client.get('/api/random?rows=1&cols=3')
    assert r.status_code == 200
    data = r.json()
    assert len(data['images']) == 3
    assert data['total'] == 5
    # Each image should be a string path
    for img in data['images']:
        assert isinstance(img, str)


def test_thumbnail_endpoint(tmp_path, monkeypatch):
    from app import config
    # Create a small PNG file that PIL can open
    png = (b'\x89PNG\r\n\x1a\n' b'\x00\x00\x00\rIHDR' b'\x00\x00\x00\x01\x00\x00\x00\x01' b'\x08\x06\x00\x00\x00' b'\x1f\x15\xc4\x89' b'\x00\x00\x00\x0bIDAT' b'\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe' b'\x00\x00\x00\x00IEND\xaeB`\x82')
    d = tmp_path / 'pics'
    d.mkdir()
    p = d / 'test.png'
    p.write_bytes(png)
    # Request direct image serving via /serve
    res = client.get(f'/serve?path={str(p)}')
    assert res.status_code == 200
    assert res.headers['content-type'].startswith('image/')


def test_thumbnail_not_found():
    res = client.get('/serve?path=C:/no/such/file.jpg')
    assert res.status_code == 404
