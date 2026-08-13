# FiremeX Edge Agent

The agent is a small program that runs **on a computer at your site**, on the
same network as your cameras. It watches the camera streams, decides locally
whether it is looking at fire or smoke, and tells the FiremeX cloud only when
something happens.

Think of it as a guard watching the monitors inside the building, who phones
head office when there's a problem — rather than piping every camera to head
office around the clock.

## Why it works this way

- **Your video stays on your network.** Only detections and a small thumbnail
  are uploaded. Full video goes up only while someone has that camera's live
  feed open on screen, and stops the moment they close it.
- **No inbound firewall rules.** The agent always dials *out* to FiremeX. The
  cloud never connects into your network, so nothing has to be port-forwarded.
- **Detection keeps working if the internet drops.** It runs locally; events
  queue and are delivered when the connection returns.

```
 YOUR SITE                                        FIREMEX CLOUD
 ┌──────────────────────────────────┐            ┌──────────────────┐
 │ Cameras ──RTSP──► Edge Agent ────┼──outbound──► dashboards       │
 │                      │           │   HTTPS    │ alerts, history  │
 │ Home Assistant ◄─────┘           │            └──────────────────┘
 └──────────────────────────────────┘
```

## What you need

A machine that stays on, on the same LAN as the cameras — a mini PC, a NUC, a
Raspberry Pi 4/5, or a VM on an existing server — with Docker installed and a
network route to the cameras. For real detection, 4 GB RAM is a sensible floor.

## Install

**1. Create a Site in FiremeX.** Sign in as an admin → **Sites → Create Site**.
Copy the enrollment token — it is shown **once**. (Lost it? Use *Rotate token*
on that site. Rotating kills the old token immediately.)

**2. Add at least one camera.** **Cameras → Add Camera.** The agent only
watches cameras registered in the app, and it reads the list once at startup —
add cameras before starting it, or restart the agent afterwards.

`stream_url` is normally `rtsp://…`, but OpenCV opens **any** URL or file path
it understands. For a demo on a machine with no CCTV, point it at an ordinary
http(s) `.mp4` and the agent treats it as a camera — it loops when the file
ends. That needs no hardware and, unlike a webcam, works inside Docker.

**3. Put two files on the machine.** The quickest route is **Get Started → Run
the edge agent** in the dashboard, which offers both as downloads already filled
in for your deployment. To write them by hand, use the `docker-compose.yml` from
this directory and an `edge.env` next to it:

```ini
FIREMEX_CLOUD_URL=https://firemex-backend.up.railway.app
AGENT_TOKEN=<the token you just copied>
DETECTOR_MODE=yolo
MODEL_PATH=/app/models/fire_model.pt
MODEL_URL=https://github.com/malika1234m/Firemax/releases/download/v0.1.0/fire_model.pt
MODEL_SHA256=2ab009042ba04827ee1cd1ccb0648832577677334c5fe4927e7c7950f7406c89
```

You do **not** need to clone this repository — the Compose file pulls a
prebuilt image.

**4. Check the connection before involving cameras:**

```bash
docker compose run --rm agent python agent.py --selftest
```

This pulls the site config, sends a heartbeat, and posts one synthetic event.
It needs no cameras and no detection model, so it isolates "is the token and
URL right, and is anything blocking the connection" from everything else.

**5. Start it:**

```bash
docker compose up -d
```

The site flips to **Online** in the FiremeX Sites page within ~10 seconds.

> **Note:** the agent reads its camera list and detection settings **once, at
> startup**. Adding a camera or changing the confidence threshold in the app
> does not reach a running agent — restart it (`docker compose restart`) to
> pick the change up.

## Modes

| `DETECTOR_MODE` | Behaviour |
|---|---|
| `yolo` | Real detection. Downloads the weights on first run when `MODEL_URL` is set, verifies `MODEL_SHA256`, and caches them. |
| `mock` | No ML at all — every loop runs but nothing is ever reported as a hazard. Use while first wiring up a site, or on low-power hardware during setup. |

## Configuration reference

Every setting is an environment variable, read from `edge.env`. The FiremeX
dashboard generates a filled-in `edge.env` for you (**Get Started → Run the edge
agent → Download**) with the cloud URL, image and model details already correct
for your deployment — that page is the source of truth, so prefer it over
copying values from here by hand.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `FIREMEX_CLOUD_URL` | yes | `http://localhost:8000` | The control plane to report to. Must be `https://` anywhere real. |
| `AGENT_TOKEN` | yes | — | Site enrollment token (Sites → Create Site). The agent exits at startup without it. |
| `DETECTOR_MODE` | no | `yolo` | `yolo` = real detection; `mock` = no ML at all, never reports a hazard. |
| `MODEL_PATH` | no | `models/fire_model.pt` | Where the weights live on this box. With the Compose file, a named volume so the download is cached. |
| `MODEL_URL` | yes for `yolo` | — | Where to fetch the weights if `MODEL_PATH` is missing. Without it the agent stops rather than run blind. |
| `MODEL_SHA256` | no | — | Pins the weights. Strongly recommended: a wrong or tampered model is a silent detection failure. |
| `HEARTBEAT_INTERVAL` | no | `10` | Seconds between heartbeats. The site shows Online while these keep arriving. |
| `WEBCAM_CAMERA_ID` | no | — | Feed one registered camera from this machine's webcam instead of its URL. Rarely works inside Docker on macOS/Windows. |
| `WEBCAM_DEVICE` | no | `0` | Which local camera device to use. Note `0` may be an iPhone via Continuity Camera on a Mac. |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Site never goes Online | Wrong `AGENT_TOKEN` or `FIREMEX_CLOUD_URL` — run `--selftest` |
| `Invalid agent token` | Token was rotated in the app; paste the new one |
| `Detection model not found` | `MODEL_URL` unset and no weights on the box — set it, or use `DETECTOR_MODE=mock` |
| Camera shows "No Signal" | The agent can't reach that RTSP URL; test it from this machine first |

Logs: `docker compose logs -f agent`

## What the agent sends

- `GET /agent/config` — its camera list, detection tuning, and the site's Home
  Assistant connection.
- `POST /agent/heartbeat` — liveness plus per-camera FPS, latency, online state.
- `POST /agent/events` — hazards detected locally, with a thumbnail.
- `WS /agent/ws` — live frames, only while an operator is watching that feed.
