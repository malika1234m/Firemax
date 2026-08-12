#!/usr/bin/env bash
# Run the edge agent on THIS Mac, against the local backend.
#
# This is the development shortcut — it uses the repo's Python venv directly
# instead of Docker, because the customer install (docker-compose.yml) needs a
# published image and a machine with disk space to spare.
#
#   ./run-local.sh              # real detection
#   ./run-local.sh --selftest   # just check the cloud connection
#   DETECTOR_MODE=mock ./run-local.sh    # run with no ML at all
#
# To feed one registered camera from this Mac's built-in webcam instead of its
# RTSP url — useful for testing detection by holding a fire video up to it:
#
#   WEBCAM_CAMERA_ID=<camera id> WEBCAM_DEVICE=1 ./run-local.sh
#
# WEBCAM_DEVICE=1 is the built-in FaceTime camera on this machine. Device 0 is
# the iPhone via Continuity Camera — using it wakes the phone up, which is
# almost never what you want here.
#
# Set AGENT_TOKEN first (Sites -> Create Site, or Rotate token):
#   export AGENT_TOKEN=paste-the-token-here
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

if [ -z "${AGENT_TOKEN:-}" ]; then
  echo "AGENT_TOKEN is not set."
  echo "  In the app: Sites -> Create Site (or Rotate token), copy the token, then:"
  echo "    export AGENT_TOKEN=<the token>"
  exit 1
fi

export FIREMEX_CLOUD_URL="${FIREMEX_CLOUD_URL:-http://localhost:8000}"
export DETECTOR_MODE="${DETECTOR_MODE:-yolo}"
export MODEL_PATH="${MODEL_PATH:-$ROOT/backend/models/fire_model.pt}"

echo "cloud    : $FIREMEX_CLOUD_URL"
echo "detector : $DETECTOR_MODE"
echo "model    : $MODEL_PATH"
echo

cd "$HERE"
exec "$ROOT/backend/.venv/bin/python" agent.py "$@"
