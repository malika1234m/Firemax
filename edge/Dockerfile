# FiremeX edge agent — runs on the customer's own network.
FROM python:3.11-slim

# OpenCV runtime deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install agent deps first (better layer caching).
COPY edge/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The agent code, plus the shared detection package it reuses.
COPY edge/ ./
COPY backend/app/ ./app/

# YOLO model is provided at deploy time (mounted or baked into a downstream image).
ENV DETECTOR_MODE=yolo \
    MODEL_PATH=models/fire_model.pt

CMD ["python", "agent.py"]
