# FiremeX — fully-local Home Assistant add-on.
#
# Detection runs here, on the Home Assistant machine. Frames come from Home
# Assistant's own camera entities and hazards are published straight back to
# Home Assistant. There is no FiremeX cloud in this deployment.
#
# Built from the REPOSITORY ROOT, because it reuses two things rather than
# reimplementing them: the shared detection package (backend/app/detection) and
# the site agent's pipeline and model-fetching code (edge/). Keeping one copy of
# the detection logic is the point — a second copy would drift, and in this
# product that means a site running a detector we thought we had replaced.
# EZVIZ support (ezviz_bridge/) is a small Node program driving EZVIZ's own web
# player in headless Chromium. Node and its one package come from the official
# Node image; both images are Debian bookworm, so the binary runs as-is.
FROM node:20-bookworm-slim AS ezviz
WORKDIR /ezviz_bridge
COPY ezviz_bridge/package.json ezviz_bridge/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund

FROM python:3.11-slim

# chromium: Debian's build exists for amd64 AND arm64 (Raspberry Pi, HA Green);
# the browser Puppeteer would download has no arm64 Linux build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 chromium fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY --from=ezviz /usr/local/bin/node /usr/local/bin/node
# The EZVIZ browser plays content from the internet, so it runs as this
# unprivileged user (see ha_agent/ezviz.py), not as root.
RUN useradd --system --no-create-home --home-dir /tmp/ezviz --shell /usr/sbin/nologin ezviz

WORKDIR /app

# Same dependency set as the site agent — deliberately, so the two cannot drift
# onto different torch/ultralytics versions and detect differently.
COPY edge/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# Verifies the cloud's signed licence answers (ha_agent/licence.py). Only the
# add-on needs it, so it is not in the edge agent's shared requirements.
RUN pip install --no-cache-dir cryptography==43.0.1

COPY edge/ ./
COPY backend/app/ ./app/
COPY ha_agent/ ./ha_agent/
COPY --from=ezviz /ezviz_bridge/node_modules ./ezviz_bridge/node_modules
COPY ezviz_bridge/package.json ezviz_bridge/bridge.mjs ezviz_bridge/config.mjs ezviz_bridge/ezviz.mjs \
     ezviz_bridge/player.html ezviz_bridge/fake_player.html ./ezviz_bridge/

# /data is the add-on's persistent volume, so weights survive add-on updates.
ENV MODEL_PATH=/data/fire_model.pt \
    PYTHONUNBUFFERED=1 \
    EZVIZ_BRIDGE=/app/ezviz_bridge/bridge.mjs \
    CHROME_PATH=/usr/bin/chromium \
    PUPPETEER_SKIP_DOWNLOAD=1

CMD ["python", "-m", "ha_agent.main"]
