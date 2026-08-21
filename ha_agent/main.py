"""FiremeX as a fully-local Home Assistant add-on.

    Cameras (any HA integration) --> Home Assistant --> FiremeX --> HA automations

Everything happens on this machine. There is no FiremeX cloud in this
deployment: no account, no enrollment token, no internet requirement after the
model has been downloaded once. Frames are read from Home Assistant's own
camera entities and hazards are published straight back to Home Assistant.

The detection itself is the SAME code the site agent runs — HazardDetector and
EdgePipeline are imported unchanged. Only the frame source and the alert
destination differ, which is exactly why both are injected rather than
hardcoded.
"""
import base64
import logging
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# The image lays the shared FiremeX code out at /app, the same as the site
# agent's, so `pipeline`, `model` and the `app.detection` package are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ha_agent import options as opts_module          # noqa: E402
from ha_agent.ha_client import HAClient              # noqa: E402
from ha_agent.ha_stream import reader_factory        # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("ha.main")

# How often to re-read Home Assistant's camera list, so a camera added in HA is
# picked up without restarting the add-on.
DISCOVERY_INTERVAL = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_detector(options):
    """The learned model plus the deterministic branches — identical to the
    site agent. Weights are fetched and checksum-verified before loading,
    because HazardDetector silently falls back to a generic COCO model when the
    file is missing, which would leave the add-on 'running' while detecting no
    fire at all."""
    if options.detector_mode != "yolo":
        logger.info("Detector: mock (no ML) — set detector_mode to 'yolo' for real detection")

        class MockDetector:
            threshold = options.confidence_threshold

            def detect(self, frame):
                return []

            def is_hazard(self, detections):
                return []

        return MockDetector()

    from model import ensure_model
    ensure_model(options.model_path, options.model_url, options.model_sha256)

    from app.detection.detector import HazardDetector
    logger.info("Detector: YOLO (real model)")
    return HazardDetector(model_path=options.model_path,
                          threshold=options.confidence_threshold)


def wanted_cameras(client: HAClient, options) -> dict:
    """Which HA camera entities to watch, keyed by entity_id."""
    available = {c["entity_id"]: c for c in client.list_cameras()}
    chosen = options.cameras

    if not chosen:
        return available

    result = {}
    for entity_id in chosen:
        if entity_id in available:
            result[entity_id] = available[entity_id]
        else:
            # Naming a camera that does not exist is a configuration mistake
            # that would otherwise be completely silent.
            logger.warning(f"configured camera '{entity_id}' is not an available "
                           f"Home Assistant camera entity — ignoring it")
    return result


def reconcile(client, options, detector, pipelines: dict, on_event):
    """Make the running pipelines match Home Assistant's camera list."""
    from pipeline import EdgePipeline

    wanted = wanted_cameras(client, options)

    for entity_id in list(pipelines):
        if entity_id not in wanted:
            pipelines.pop(entity_id).stop()
            logger.info(f"camera removed: {entity_id}")

    for entity_id, cam in wanted.items():
        if entity_id in pipelines:
            continue
        pipeline = EdgePipeline(
            {"camera_id": entity_id, "name": cam["name"],
             "zone": "Home Assistant", "stream_url": entity_id},
            detector, on_event,
            options.confidence_threshold, options.alert_cooldown_seconds,
            process_fps=options.process_fps,
            reader_factory=reader_factory(client),
        )
        pipeline.start()
        pipelines[entity_id] = pipeline
        logger.info(f"camera added: {cam['name']} ({entity_id})")


def run():
    options = opts_module.load()
    logger.info(f"FiremeX Home Assistant add-on v{opts_module.ADDON_VERSION} — fully local")
    logger.info(f"  detector={options.detector_mode}  threshold={options.confidence_threshold}  "
                f"cooldown={options.alert_cooldown_seconds}s  model={options.model_path}")

    client = HAClient()
    if not client.token:
        raise SystemExit(
            "No SUPERVISOR_TOKEN. This add-on must run under the Home Assistant "
            "Supervisor with 'homeassistant_api: true' in its configuration."
        )
    if not client.ping():
        raise SystemExit("Could not reach Home Assistant. Is the Supervisor healthy?")

    detector = build_detector(options)

    last_hazard = {"at": 0.0}

    def on_event(event: dict):
        """A confirmed hazard from any camera. EdgePipeline has already applied
        the confidence threshold and the per-camera cooldown."""
        last_hazard["at"] = time.time()
        logger.warning(f"HAZARD {event['hazard_type']} on {event['camera_name']} "
                       f"({event['confidence']:.0%})")
        client.publish_hazard(
            hazard_type=event["hazard_type"],
            camera_name=event["camera_name"],
            confidence=float(event["confidence"]),
            entity_id=event["camera_id"],
            timestamp=_now_iso(),
        )

    pipelines: dict = {}
    reconcile(client, options, detector, pipelines, on_event)
    if not pipelines:
        logger.warning("No Home Assistant camera entities to watch yet — "
                       "add a camera integration in Home Assistant and it will "
                       "be picked up automatically.")
    else:
        logger.info(f"watching {len(pipelines)} camera(s)")

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    client.publish_clear(_now_iso())      # start from a known state
    cleared = True
    last_discovery = time.time()

    while not stop.is_set():
        now = time.time()

        # Return the sensor to "clear" after a quiet period. A Home Assistant
        # sensor is a STATE, not a log line — left on "fire" forever, every
        # dashboard and template condition reading it would be wrong.
        if not cleared and last_hazard["at"] and \
                now - last_hazard["at"] >= options.clear_after_seconds:
            client.publish_clear(_now_iso())
            cleared = True
            logger.info("hazard cleared")
        elif last_hazard["at"] and now - last_hazard["at"] < options.clear_after_seconds:
            cleared = False

        if now - last_discovery >= DISCOVERY_INTERVAL:
            last_discovery = now
            try:
                reconcile(client, options, detector, pipelines, on_event)
            except Exception as exc:
                # A failed poll must never tear down working pipelines.
                logger.warning(f"camera discovery failed, keeping current set: {exc}")

        stop.wait(1.0)

    logger.info("shutting down…")
    for p in pipelines.values():
        p.stop()
    client.close()


if __name__ == "__main__":
    run()
