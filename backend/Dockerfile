# Build context is the REPO ROOT, not backend/ — same convention as
# edge/Dockerfile. A monorepo host (and Railway in particular) uploads the
# whole repository and builds from its root, so a Dockerfile that assumes its
# own directory as context cannot find its files there.
#
#   docker build -f backend/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

# libgl1/libglib2.0-0 are OpenCV runtime deps. The control plane no longer
# imports cv2 (detection moved to the edge agent), but seeding scripts and the
# optional dev extras still can, and these are a few MB.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# Dependencies first so the layer caches across code edits.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Railway and most PaaS hosts inject $PORT; default to 8000 for Compose.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
