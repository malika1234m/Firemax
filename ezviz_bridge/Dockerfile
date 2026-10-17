# FiremeX EZVIZ bridge — Home Assistant add-on image.
#
# Runs EZVIZ's official web player (EZUIKit) in headless Chromium to play
# encrypted EZVIZ cameras, and serves the decoded pictures as MJPEG cameras.
# Built from this folder:   docker build -t firemex-ezviz-bridge ezviz_bridge
FROM node:20-bookworm-slim

# Debian's Chromium exists for both amd64 and arm64 (Raspberry Pi, HA Green);
# the browser Puppeteer would download does not exist for arm64 Linux.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund
COPY bridge.mjs config.mjs ezviz.mjs homeassistant.mjs player.html fake_player.html ./

ENV CHROME_PATH=/usr/bin/chromium \
    PUPPETEER_SKIP_DOWNLOAD=1 \
    NODE_ENV=production

EXPOSE 8095
CMD ["node", "bridge.mjs"]
