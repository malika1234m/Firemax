"""FiremeX as a fully-local Home Assistant add-on.

    Cameras (any HA integration) --> Home Assistant --> FiremeX --> operator --> automations

Everything happens on this machine. There is no FiremeX cloud in this
deployment: no account, no enrollment token, no internet requirement after the
model has been downloaded once.

IMPORTANT — what this add-on does NOT do:

FiremeX raises ALERTS. It never declares an incident, and nothing it publishes
should be wired directly to a sprinkler or a phone call. A detection is a
machine's opinion; an operator confirms it and presses "Declare incident", and
only that turns on the actuators. This mirrors the cloud product, where
automations and authority calls fire from /alerts/{id}/promote and never from a
raw detection. The reason is the model's own error profile: it is confident and
sometimes wrong, and a false sprinkler discharge is its own emergency.

The detection code is the SAME code the site agent runs — HazardDetector and
EdgePipeline are imported unchanged. Only the frame source and the alert
destination differ, which is why both are injected rather than hardcoded.
"""
import base64
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ha_agent import options as opts_module          # noqa: E402
from ha_agent.ha_client import HAClient, OFFLINE_HAZARD  # noqa: E402
from ha_agent.ha_stream import reader_factory        # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("ha.main")

# How often to re-read Home Assistant's camera list, so a camera added in HA is
# picked up without restarting the add-on.
DISCOVERY_INTERVAL = 60
# How often per-camera status is pushed, which is what the camera wall reads.
CAMERA_PUBLISH_INTERVAL = 5


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClassFilteredDetector:
    """Wraps the shared detector so only chosen hazard classes raise an alert.

    Filtering happens at is_hazard(), not detect(), so every branch still runs
    and every box is still available — what changes is which of them an
    operator is asked to act on. That also means the evidence snapshot shows
    exactly the detections that triggered the alert, not a picture cluttered
    with boxes the system decided to ignore.
    """

    def __init__(self, inner, allowed):
        self._inner = inner
        self._allowed = {c.strip().lower() for c in allowed if c and c.strip()}

    @property
    def threshold(self):
        return getattr(self._inner, "threshold", None)

    @threshold.setter
    def threshold(self, value):
        self._inner.threshold = value

    def detect(self, frame):
        return self._inner.detect(frame)

    def is_hazard(self, detections):
        return [d for d in self._inner.is_hazard(detections)
                if d.label.lower() in self._allowed]


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
    detector = HazardDetector(model_path=options.model_path,
                              threshold=options.confidence_threshold)
    allowed = options.hazard_classes
    logger.info(f"Detector: YOLO (real model)  alerting on: {', '.join(allowed)}")
    return ClassFilteredDetector(detector, allowed)


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
            logger.warning(f"configured camera '{entity_id}' is not an available "
                           f"Home Assistant camera entity — ignoring it")
    return result


def write_snapshot(directory: str, entity_id: str, frame_b64: str | None) -> str | None:
    """Save the annotated detection frame and return the URL Home Assistant
    serves it at.

    EdgePipeline already draws the boxes (edge/pipeline.py annotate()), so what
    lands here is what the model actually saw, not a bare photograph. That
    distinction is the whole point: an operator being asked to declare an
    incident needs to see WHY, and a confidence number alone is not reviewable.

    Written to a temp file and renamed, so a half-written JPEG is never served
    to an operator mid-decision.
    """
    if not frame_b64:
        return None
    try:
        os.makedirs(directory, exist_ok=True)
        slug = entity_id.split(".", 1)[-1]
        path = os.path.join(directory, f"{slug}.jpg")
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(base64.b64decode(frame_b64))
        os.replace(tmp, path)
        return f"/local/firemex/{slug}.jpg"
    except Exception as exc:
        logger.warning(f"could not write snapshot for {entity_id}: {exc}")
        return None


class CameraState:
    """What the operator's camera wall needs to know about one camera."""

    def __init__(self, name: str):
        self.name = name
        self.hazard = "clear"
        self.confidence = 0.0
        self.last_detection = None
        self.last_hazard_at = 0.0
        self.snapshot_url = None
        self.started_at = time.time()
        self.offline_alerted = False


def reconcile(client, options, detector, pipelines: dict, states: dict, on_event):
    """Make the running pipelines match Home Assistant's camera list."""
    from pipeline import EdgePipeline

    wanted = wanted_cameras(client, options)

    for entity_id in list(pipelines):
        if entity_id not in wanted:
            pipelines.pop(entity_id).stop()
            states.pop(entity_id, None)
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
        states[entity_id] = CameraState(cam["name"])
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

    # Set up the operator workflow before detecting anything. A client who
    # installs the add-on and presses Start should get the dashboard, the
    # helpers and the automations without running a script — and detection is
    # useless to them until there is somewhere to review an alert.
    if options.provision_dashboard:
        try:
            from ha_agent import setup_ha
            setup_ha.main(url=client.base_url.removesuffix("/api"),
                          token=client.token,
                          snapshot_dir=options.snapshot_dir,
                          ha_config_dir=options.ha_config_dir)
        except SystemExit as exc:
            # No cameras yet is the normal first-run case, not a failure: the
            # agent keeps running and picks them up when they appear.
            logger.warning(f"provisioning skipped: {exc}")
        except Exception:
            # Never let dashboard setup stop detection from starting.
            logger.exception("provisioning failed; continuing without it")

    detector = build_detector(options)

    states: dict[str, CameraState] = {}
    last_hazard = {"at": 0.0}
    lock = threading.Lock()

    def on_event(event: dict):
        """A confirmed hazard from one camera. EdgePipeline has already applied
        the confidence threshold and the per-camera cooldown."""
        entity_id = event["camera_id"]
        snapshot = (write_snapshot(options.snapshot_dir, entity_id, event.get("frame_b64"))
                    if options.save_snapshots else None)
        with lock:
            last_hazard["at"] = time.time()
            st = states.get(entity_id)
            if st:
                st.hazard = event["hazard_type"]
                st.confidence = float(event["confidence"])
                st.last_detection = _now_iso()
                st.last_hazard_at = time.time()
                st.snapshot_url = snapshot
        logger.warning(f"ALERT {event['hazard_type']} on {event['camera_name']} "
                       f"({event['confidence']:.0%}) — awaiting operator review")
        client.publish_hazard(
            hazard_type=event["hazard_type"],
            camera_name=event["camera_name"],
            confidence=float(event["confidence"]),
            entity_id=entity_id,
            timestamp=_now_iso(),
            snapshot=snapshot,
        )

    pipelines: dict = {}
    reconcile(client, options, detector, pipelines, states, on_event)
    if not pipelines:
        logger.warning("No Home Assistant camera entities to watch yet — add a "
                       "camera integration in Home Assistant and it will be "
                       "picked up automatically.")
    else:
        logger.info(f"watching {len(pipelines)} camera(s)")

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    client.publish_clear(_now_iso())
    cleared = True
    last_discovery = last_publish = time.time()

    while not stop.is_set():
        now = time.time()

        # Global hazard sensor returns to "clear" after a quiet period. A Home
        # Assistant sensor is a STATE, not a log line — left on "fire" forever,
        # every dashboard and template condition reading it would be wrong.
        with lock:
            since = now - last_hazard["at"] if last_hazard["at"] else None
        if since is not None and not cleared and since >= options.clear_after_seconds:
            client.publish_clear(_now_iso())
            cleared = True
            logger.info("hazard cleared")
        elif since is not None and since < options.clear_after_seconds:
            cleared = False

        # Per-camera status for the operator's camera wall, plus offline alerts.
        if now - last_publish >= CAMERA_PUBLISH_INTERVAL:
            last_publish = now
            for entity_id, pipeline in list(pipelines.items()):
                st = states.get(entity_id)
                if st is None:
                    continue
                health = pipeline.health()
                online = bool(health["online"])

                # A camera is only judged offline after a grace period — at
                # startup it has legitimately never delivered a frame yet, and
                # alerting then would cry wolf on every restart.
                past_grace = (now - st.started_at) >= options.camera_offline_after_seconds
                if not online and past_grace and not st.offline_alerted:
                    st.offline_alerted = True
                    st.hazard = OFFLINE_HAZARD
                    logger.warning(f"ALERT camera_offline on {st.name} — no frames for "
                                   f"{health['last_frame_age_s']}s")
                    client.publish_camera_offline(entity_id, st.name, _now_iso(),
                                                  health["last_frame_age_s"])
                elif online and st.offline_alerted:
                    st.offline_alerted = False
                    st.hazard = "clear"
                    logger.info(f"camera recovered: {st.name}")

                # Per-camera hazard also expires, so the wall does not show a
                # camera as burning ten minutes after the fact.
                if (st.hazard not in ("clear", OFFLINE_HAZARD) and st.last_hazard_at
                        and now - st.last_hazard_at >= options.clear_after_seconds):
                    st.hazard = "clear"
                    st.confidence = 0.0

                client.publish_camera(entity_id, st.name, st.hazard, st.confidence,
                                      online, health["fps"], st.last_detection,
                                      st.snapshot_url)

        if now - last_discovery >= DISCOVERY_INTERVAL:
            last_discovery = now
            try:
                reconcile(client, options, detector, pipelines, states, on_event)
            except Exception as exc:
                logger.warning(f"camera discovery failed, keeping current set: {exc}")

        stop.wait(1.0)

    logger.info("shutting down…")
    for p in pipelines.values():
        p.stop()
    client.close()


if __name__ == "__main__":
    run()
