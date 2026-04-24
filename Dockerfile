FROM python:3.13-slim

WORKDIR /app

# Copy dependency manifests first so this layer is cached unless deps change
COPY pyproject.toml poetry.lock README.md ./

# Install dependencies ahead of the app code for better cache reuse
RUN pip install --no-cache-dir \
    "pillow>=11.3.0,<12.0.0" \
    "fastapi>=0.112.0,<1.0.0" \
    "starlette>=0.41.0,<1.0.0" \
    "uvicorn[standard]>=0.30.0,<1.0.0" \
    "jinja2>=3.1.0,<4.0.0" \
    "python-multipart>=0.0.9,<1.0.0" \
    "httpx>=0.24.0,<1.0.0"

# Copy application source and install the package (no-deps: already installed above)
COPY app/ ./app/
RUN pip install --no-cache-dir --no-deps .

# Declare mount points
# /photos  – mount your image library here (or override GALLERY_ROOT)
# /cache   – persist the thumbnail cache across container restarts
VOLUME ["/photos"]
VOLUME ["/cache"]

ENV GALLERY_ROOT=/photos
ENV GALLERY_CACHE=/cache
ENV GALLERY_HOST=0.0.0.0
ENV GALLERY_PORT=8000

EXPOSE 8000

CMD ["gallery"]
