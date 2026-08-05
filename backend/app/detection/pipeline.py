import asyncio
import base64
import threading
import time
import logging
from datetime import datetime
import cv2
import numpy as np

from app.detection.stream import StreamReader
from app.detection.detector import HazardDetector
from app.config import settings
from app.models import Alert, WSFrame, DetectionBox

logger = logging.getLogger(__name__)

DEFAULT_ALERT_COOLDOWN_SECONDS = 30   # minimum gap between alerts for the same camera
OFFLINE_THRESHOLD_SECONDS = 15   # how long a stream must be dark before we alert


class CameraPipeline:
    """
    Full pipeline for one camera:
      StreamReader → HazardDetector → WebSocket broadcast + alert saving

    confidence_threshold/alert_cooldown_seconds come from the owning org's
    Settings (Organization.confidence_threshold / alert_cooldown_seconds) —
    the shared HazardDetector's own internal threshold is a permissive lower
    bound; this is the per-org bar for whether a detection becomes an alert.
    """

    def __init__(self, camera_id: str, camera_name: str, stream_url: str,
                 detector: HazardDetector, broadcast_fn, save_alert_fn, org_id: str, zone: str = "Unassigned",
                 confidence_threshold: float = None, alert_cooldown_seconds: int = DEFAULT_ALERT_COOLDOWN_SECONDS):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.stream_url = stream_url
        self.org_id = org_id
        self.zone = zone
        self.detector = detector
        self.broadcast_fn = broadcast_fn     # async fn(camera_id, WSFrame)
        self.save_alert_fn = save_alert_fn   # async fn(Alert)
        self.confidence_threshold = confidence_threshold
        self.alert_cooldown_seconds = alert_cooldown_seconds

        self.reader = StreamReader(stream_url)
        self._running = False
        self._thread: threading.Thread = None
        self._last_alert_time: float = 0
        self._loop: asyncio.AbstractEventLoop = None
        # Live health metrics surfaced on the platform console.
        self.current_fps: float = 0.0
        self.avg_inference_ms: float = 0.0
        self._offline_since: float = None
        self._offline_alerted = False

    def start(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._running = True
        self.reader.start()
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        logger.info(f"Pipeline started: {self.camera_id} ({self.stream_url})")

    def stop(self):
        self._running = False
        self.reader.stop()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"Pipeline stopped: {self.camera_id}")

    def _process_loop(self):
        interval = 1.0 / settings.PROCESS_FPS
        frame_count = 0
        fps_timer = time.time()

        while self._running:
            start = time.time()

            frame = self.reader.get_frame()
            if frame is None:
                now = time.time()
                if self._offline_since is None:
                    self._offline_since = now
                elif not self._offline_alerted and now - self._offline_since >= OFFLINE_THRESHOLD_SECONDS:
                    self._offline_alerted = True
                    alert = Alert(
                        org_id=self.org_id,
                        camera_id=self.camera_id,
                        camera_name=self.camera_name,
                        hazard_type="camera_offline",
                        confidence=1.0,
                        zone=self.zone,
                    )
                    asyncio.run_coroutine_threadsafe(self.save_alert_fn(alert), self._loop)
                time.sleep(0.1)
                continue

            if self._offline_since is not None:
                self._offline_since = None
                self._offline_alerted = False

            _infer_start = time.time()
            detections = self.detector.detect(frame)
            infer_ms = (time.time() - _infer_start) * 1000
            # Exponential moving average so a single slow frame doesn't spike it.
            self.avg_inference_ms = infer_ms if self.avg_inference_ms == 0 else 0.8 * self.avg_inference_ms + 0.2 * infer_ms

            hazards = self.detector.is_hazard(detections)
            if self.confidence_threshold is not None:
                hazards = [h for h in hazards if h.confidence >= self.confidence_threshold]

            annotated = self._draw_boxes(frame.copy(), detections)

            frame_count += 1
            elapsed = time.time() - fps_timer
            fps = frame_count / elapsed if elapsed > 0 else 0
            self.current_fps = fps
            if elapsed >= 5:
                frame_count = 0
                fps_timer = time.time()

            _, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(jpeg.tobytes()).decode()

            ws_frame = WSFrame(
                camera_id=self.camera_id,
                frame_b64=frame_b64,
                detections=detections,
                fps=round(fps, 1),
                timestamp=datetime.utcnow().isoformat(),
            )

            asyncio.run_coroutine_threadsafe(
                self.broadcast_fn(self.camera_id, ws_frame),
                self._loop,
            )

            if hazards:
                now = time.time()
                if now - self._last_alert_time >= self.alert_cooldown_seconds:
                    self._last_alert_time = now
                    top = max(hazards, key=lambda d: d.confidence)
                    alert = Alert(
                        org_id=self.org_id,
                        camera_id=self.camera_id,
                        camera_name=self.camera_name,
                        hazard_type=top.label,
                        confidence=top.confidence,
                        frame_b64=frame_b64,
                        zone=self.zone,
                    )
                    asyncio.run_coroutine_threadsafe(
                        self.save_alert_fn(alert),
                        self._loop,
                    )

            sleep = interval - (time.time() - start)
            if sleep > 0:
                time.sleep(sleep)

    def _draw_boxes(self, frame: np.ndarray, detections: list[DetectionBox]) -> np.ndarray:
        HAZARD_COLOR = (0, 0, 255)    # red for hazards
        NORMAL_COLOR = (0, 255, 0)    # green for other detections

        for d in detections:
            is_hazard = d.label.lower() in {"fire", "smoke", "flame"}
            color = HAZARD_COLOR if is_hazard else NORMAL_COLOR
            cv2.rectangle(frame, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), color, 2)
            label_text = f"{d.label} {d.confidence:.0%}"
            cv2.putText(frame, label_text, (int(d.x1), int(d.y1) - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        return frame


class CameraManager:
    """Singleton that manages all active camera pipelines."""

    def __init__(self):
        self._pipelines: dict[str, CameraPipeline] = {}
        self._detector = HazardDetector()

    def start_camera(self, camera_id: str, camera_name: str, stream_url: str,
                     loop, broadcast_fn, save_alert_fn, org_id: str, zone: str = "Unassigned",
                     confidence_threshold: float = None, alert_cooldown_seconds: int = DEFAULT_ALERT_COOLDOWN_SECONDS):
        if camera_id in self._pipelines:
            return
        pipeline = CameraPipeline(
            camera_id=camera_id,
            camera_name=camera_name,
            stream_url=stream_url,
            detector=self._detector,
            broadcast_fn=broadcast_fn,
            save_alert_fn=save_alert_fn,
            org_id=org_id,
            zone=zone,
            confidence_threshold=confidence_threshold,
            alert_cooldown_seconds=alert_cooldown_seconds,
        )
        pipeline.start(loop)
        self._pipelines[camera_id] = pipeline

    def stop_camera(self, camera_id: str):
        pipeline = self._pipelines.pop(camera_id, None)
        if pipeline:
            pipeline.stop()

    def update_org_settings(self, org_id: str, confidence_threshold: float, alert_cooldown_seconds: int):
        """Push new detection settings to every already-running pipeline for
        this org, so a Settings change applies immediately — no camera
        restart needed."""
        for pipeline in self._pipelines.values():
            if pipeline.org_id == org_id:
                pipeline.confidence_threshold = confidence_threshold
                pipeline.alert_cooldown_seconds = alert_cooldown_seconds

    def stop_all(self):
        for pipeline in list(self._pipelines.values()):
            pipeline.stop()
        self._pipelines.clear()

    def active_ids(self) -> list[str]:
        return list(self._pipelines.keys())

    def health(self) -> dict[str, dict]:
        """Live per-camera pipeline health, keyed by camera_id — for the
        platform monitoring console."""
        out = {}
        for cid, p in self._pipelines.items():
            age = p.reader.last_frame_age()
            out[cid] = {
                "org_id": p.org_id,
                "fps": round(p.current_fps, 1),
                "inference_ms": round(p.avg_inference_ms, 1),
                "last_frame_age_s": round(age, 1) if age is not None else None,
                "online": age is not None and age < OFFLINE_THRESHOLD_SECONDS,
            }
        return out

    def detector_info(self) -> dict:
        return {"model_loaded": self._detector is not None}


camera_manager = CameraManager()
