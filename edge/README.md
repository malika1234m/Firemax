# FiremeX Edge Agent

Runs on a customer's own network (a small box/VM on the same LAN as the
cameras). It reads local RTSP/IP camera streams, runs fire/hazard detection
**locally**, and reports events + health to the FiremeX cloud over outbound
HTTPS. Camera video never leaves the site — only detections and small alert
thumbnails are sent up.

## How it fits
```
 Cameras (LAN)  ──►  Edge Agent  ──(outbound HTTPS)──►  FiremeX Cloud
 Home Assistant ◄──   (this app)                         (dashboards, alerts)
```
The cloud never connects *into* the customer network, so no inbound firewall
ports are required.

## Setup
1. In FiremeX (as an admin): **Sites → Create Site** → copy the enrollment token.
2. Copy `.env.example` to `.env` and set `AGENT_TOKEN`, `FIREMEX_CLOUD_URL`.
3. Run it:
   ```bash
   # quick connectivity check (no cameras/ML needed)
   AGENT_TOKEN=... FIREMEX_CLOUD_URL=http://localhost:8000 python agent.py --selftest

   # normal run
   python agent.py
   # or:  docker build -f edge/Dockerfile -t firemex-agent . && docker run --env-file edge/.env firemex-agent
   ```
4. The site flips to **Online** in the FiremeX Sites page once heartbeats arrive.

## Modes
- `DETECTOR_MODE=yolo` — real detection using the shared FiremeX model (needs
  `torch`/`ultralytics` and the `.pt` model on the box).
- `DETECTOR_MODE=mock` — no ML; runs the loops without detecting. Good for
  first-time wiring and low-power hardware during setup.

## What it sends
- `GET /agent/config` — pulls cameras, detection tuning, and the site's Home
  Assistant connection.
- `POST /agent/heartbeat` — liveness + per-camera FPS/latency/online.
- `POST /agent/events` — hazards detected locally (with a thumbnail).
