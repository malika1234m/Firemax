"""FiremeX edge agent.

Runs on the customer's own network. On start it enrolls with its site token,
pulls its config from the cloud, runs detection locally on the site's cameras,
and reports events + health back — all over outbound HTTPS.

Usage:
  AGENT_TOKEN=... FIREMEX_CLOUD_URL=http://cloud python agent.py
  python agent.py --selftest      # verify cloud connectivity without cameras
"""
import logging
import signal
import sys
import threading
import time
from pathlib import Path

from config import AgentConfig, AGENT_VERSION
from cloud import CloudClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("edge.agent")

# Make the shared FiremeX detection package importable (monorepo dev). In the
# Docker image this package is copied in and already on the path.
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if _BACKEND.exists():
    sys.path.insert(0, str(_BACKEND))


def _selftest(client: CloudClient):
    """Prove config + heartbeat + event delivery to the cloud without needing
    any cameras or ML — the fastest way to confirm a new site is wired up."""
    logger.info("SELF-TEST: pulling config…")
    cfg = client.get_config()
    logger.info(f"  site_id={cfg['site_id']}  cameras={len(cfg['cameras'])}  "
                f"ha_configured={bool(cfg['home_assistant'].get('url'))}")

    logger.info("SELF-TEST: sending heartbeat…")
    ok = client.post_heartbeat(AGENT_VERSION, [{"camera_id": "selftest", "fps": 0, "online": False}])
    logger.info(f"  heartbeat ok={ok}")

    logger.info("SELF-TEST: sending a synthetic event…")
    created = client.post_events([{
        "camera_id": "selftest", "camera_name": "Self-Test Camera",
        "hazard_type": "smoke", "confidence": 0.42, "zone": "Self-Test",
    }])
    logger.info(f"  events created in cloud={created}")
    logger.info("SELF-TEST complete." if created else "SELF-TEST: event not stored — check token/URL.")


def run():
    cfg = AgentConfig
    cfg.require_token()
    client = CloudClient(cfg.cloud_url, cfg.token)

    if "--selftest" in sys.argv:
        _selftest(client)
        return

    from detector import build_detector
    from pipeline import EdgePipeline
    from relay import RelayClient

    logger.info(f"FiremeX edge agent v{AGENT_VERSION} → {cfg.cloud_url}")
    remote = client.get_config()
    cameras = remote["cameras"]
    det = remote["detection"]
    detector = build_detector(cfg.detector_mode, det["confidence_threshold"])

    # Thread-safe outbound event buffer (retries if the cloud is unreachable).
    events, lock = [], threading.Lock()
    def on_event(e):
        with lock:
            events.append(e)

    # Live-feed relay: persistent WS carrying frames up / stream commands down.
    by_id = {}
    relay = RelayClient(cfg.cloud_url, cfg.token,
                        on_command=lambda kind, cam: _set_streaming(by_id, kind, cam))
    def on_frame(camera_id, frame_b64, fps):
        relay.send_frame(camera_id, frame_b64, fps)

    pipelines = []
    for cam in cameras:
        # Local-webcam testing: feed the chosen camera from the webcam device.
        if cfg.webcam_camera_id and cam["camera_id"] == cfg.webcam_camera_id:
            cam = {**cam, "stream_url": cfg.webcam_device}   # int → OpenCV opens the local camera
            logger.info(f"using local webcam (device {cfg.webcam_device}) for '{cam['name']}'")
        p = EdgePipeline(cam, detector, on_event, det["confidence_threshold"], det["alert_cooldown_seconds"],
                         on_frame=on_frame)
        p.start()
        pipelines.append(p)
        by_id[p.camera_id] = p
    relay.start()
    logger.info(f"watching {len(pipelines)} camera(s); live relay active")

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    last_heartbeat = 0.0
    while not stop.is_set():
        now = time.time()
        # flush buffered events
        with lock:
            batch, events[:] = events[:], []
        if batch:
            sent = client.post_events(batch)
            if sent < len(batch):        # cloud unreachable → requeue
                with lock:
                    events[:0] = batch
        # heartbeat on interval
        if now - last_heartbeat >= cfg.heartbeat_interval:
            client.post_heartbeat(AGENT_VERSION, [p.health() for p in pipelines])
            last_heartbeat = now
        stop.wait(1.0)

    logger.info("shutting down…")
    relay.stop()
    for p in pipelines:
        p.stop()


def _set_streaming(by_id: dict, kind: str, camera_id: str):
    p = by_id.get(camera_id)
    if p:
        p.streaming = (kind == "stream_start")
        logger.info(f"live stream {'ON' if p.streaming else 'OFF'} for {p.camera_name}")


if __name__ == "__main__":
    run()
