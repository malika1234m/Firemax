# FiremeX Fire & Smoke Detection

Watches the cameras on your network for fire and smoke, using a YOLOv8 model
that runs **on this machine**. Only detections are sent to FiremeX — your video
stays on your own network.

## Requirements

This is a Home Assistant **add-on**, so it needs Home Assistant **OS** or
**Supervised**. Home Assistant **Container** has no Supervisor and therefore no
add-on support at all — if that is your install, use the Docker Compose route
in [`edge/`](https://github.com/malika1234m/Firemax/tree/main/edge) instead.
Both routes run the identical agent.

For real detection, 4 GB RAM is a sensible floor.

## Setup

**1. Create a Site in FiremeX.** Sign in as an admin, then **Sites → Create
Site**. Copy the enrollment token — it is shown **once**. (Lost it? Use
*Rotate token* on that site; rotating kills the old token immediately.)

**2. Add at least one camera.** **Cameras → Add Camera.** The agent only
watches cameras registered in the app. It re-reads the list every 30 seconds,
so cameras added later are picked up without restarting the add-on.

**3. Configure this add-on.** Open the **Configuration** tab and paste the
enrollment token into `agent_token`. Everything else already has a working
default.

**4. Start it** and watch the **Log** tab. A healthy start looks like:

```
[ha] FiremeX add-on v0.2.0 — configuration read from /data/options.json
[edge.model] model verified: /data/fire_model.pt
[edge.detector] Detector: YOLO (real model)
[edge.agent] watching 2 camera(s); live relay active
```

## Options

| Option | What it does |
|---|---|
| `cloud_url` | Your FiremeX deployment. Leave as-is unless you self-host. |
| `agent_token` | **Required.** The enrollment token from Sites → Create Site. |
| `detector_mode` | `yolo` for real detection. `mock` runs everything except the model — use it to prove the connection works on a box that can't yet run inference. |
| `model_url` | Where the weights are downloaded from on first start. |
| `model_sha256` | Verifies the download. **Leave this set.** On a mismatch the agent refuses to start, which is the correct behaviour — a swapped or corrupted model is a silent detection failure. |
| `heartbeat_interval` | Seconds between liveness reports. FiremeX marks a site offline after 45 s of silence, so leave this well below that. |
| `config_poll_interval` | Seconds between re-reading the camera list and detection tuning. |

The confidence threshold and alert cooldown are **not** set here — they are
per-organisation settings in the FiremeX app (**Settings → Detection**), and
changes reach a running add-on within `config_poll_interval` seconds.

## Where the model is stored

The weights are downloaded once to `/data/fire_model.pt`. `/data` survives both
restarts and add-on updates, so this does not re-download on every update.

## Networking

The add-on runs with host networking so it can reach cameras on your LAN. It
only ever makes **outbound** connections to FiremeX — no ports are opened and
no port forwarding or firewall rule is needed.

## Troubleshooting

**"No enrollment token set"** — `agent_token` is empty. Paste the token from
Sites → Create Site into the Configuration tab and restart.

**401 Unauthorized in the log** — the token is wrong, or it was rotated in the
app. Rotate it again and paste the new value.

**"Detection model not found … MODEL_URL is not set"** — clear `model_url` back
to its default, or set `detector_mode` to `mock` while you sort it out.

**Checksum mismatch** — the download is corrupt or the published weights
changed. Delete `/data/fire_model.pt` to force a re-download, or correct
`model_sha256`.

**Cameras show offline in FiremeX** — the agent cannot open the RTSP stream.
Check the `stream_url` in **Cameras**, and that this machine can reach the
camera's IP.
