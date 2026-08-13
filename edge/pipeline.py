"""Per-camera detection pipeline for the edge agent.

Mirrors the cloud's old CameraPipeline, but instead of writing to a database
it hands each confirmed hazard to an on_event callback (which the agent posts
up to the cloud). Frames never leave this process except as a small JPEG
thumbnail attached to an actual detection.
"""
import base64
import logging
import threading
import time

logger = logging.getLogger("edge.pipeline")

OFFLINE_THRESHOLD_SECONDS = 15

# BGR, matching the hazard colours documented in ARCHITECTURE.md. Grouped by
# what produced the detection so an operator can read the mechanism off the
# picture: red for the learned fire/smoke classes, blue/green for the
# colour-rule gas classes, yellow for optical flow, purple for geometry.
HAZARD_COLOURS = {
    "fire":          (0, 0, 255),
    "flame":         (0, 0, 255),
    "smoke":         (0, 140, 255),
    "gas_fire":      (255, 140, 0),
    "lpg_fire":      (255, 90, 90),
    "chemical_fire": (0, 200, 0),
    "gas_shimmer":   (0, 215, 255),
    "person_down":   (200, 0, 200),
}
_DEFAULT_COLOUR = (200, 200, 200)


def annotate(frame, detections):
    """Draw labelled boxes on a COPY of the frame.

    Used for the snapshot attached to an alert, so a reviewer sees what the
    model actually saw rather than a bare photograph — the snapshot is the
    evidence someone judges a true/false alarm on. The live feed draws its own
    boxes in the browser from the same coordinates, which keeps the streamed
    JPEG clean and lets the boxes stay crisp at any display size.
    """
    import cv2

    out = frame.copy()
    for d in detections:
        colour = HAZARD_COLOURS.get(d.label.lower(), _DEFAULT_COLOUR)
        x1, y1, x2, y2 = int(d.x1), int(d.y1), int(d.x2), int(d.y2)
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)

        label = f"{d.label.replace('_', ' ')} {d.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        # Keep the caption inside the frame when the box touches the top edge.
        top = max(y1, th + 6)
        cv2.rectangle(out, (x1, top - th - 6), (x1 + tw + 6, top), colour, -1)
        cv2.putText(out, label, (x1 + 3, top - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return out


class EdgePipeline:
    def __init__(self, camera: dict, detector, on_event, confidence_threshold: float, cooldown_seconds: int,
                 on_frame=None, live_fps: float = 5.0):
        self.camera_id = camera["camera_id"]
        self.camera_name = camera["name"]
        self.zone = camera.get("zone", "Unassigned")
        self.stream_url = camera["stream_url"]
        self.detector = detector
        self.on_event = on_event
        self.confidence_threshold = confidence_threshold
        self.cooldown_seconds = cooldown_seconds
        # Live-feed relay: only stream frames up while an operator is watching.
        self.on_frame = on_frame
        self.streaming = False
        self._live_interval = 1.0 / live_fps
        self._last_streamed = 0.0

        # StreamReader (OpenCV) imported lazily so self-test / mock paths don't
        # need cv2 or the shared package.
        from app.detection.stream import StreamReader
        self.reader = StreamReader(self.stream_url)

        self._running = False
        self._thread = None
        self._last_alert_time = 0.0
        self.current_fps = 0.0
        self.avg_inference_ms = 0.0

    def start(self):
        self._running = True
        self.reader.start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"pipeline started: {self.camera_name} ({self.stream_url})")

    def stop(self):
        self._running = False
        self.reader.stop()

    def _loop(self):
        import cv2
        frame_count, fps_timer = 0, time.time()
        while self._running:
            frame = self.reader.get_frame()
            if frame is None:
                time.sleep(0.2)
                continue

            t0 = time.time()
            detections = self.detector.detect(frame)
            infer_ms = (time.time() - t0) * 1000
            self.avg_inference_ms = infer_ms if self.avg_inference_ms == 0 else 0.8 * self.avg_inference_ms + 0.2 * infer_ms

            hazards = [h for h in self.detector.is_hazard(detections) if h.confidence >= self.confidence_threshold]

            frame_count += 1
            elapsed = time.time() - fps_timer
            self.current_fps = frame_count / elapsed if elapsed > 0 else 0
            if elapsed >= 5:
                frame_count, fps_timer = 0, time.time()

            # Live-feed relay: stream throttled frames up only while watched.
            if self.streaming and self.on_frame is not None:
                now = time.time()
                if now - self._last_streamed >= self._live_interval:
                    self._last_streamed = now
                    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ok:
                        # Coordinates travel with the frame; the browser draws
                        # them. Sending the clean JPEG keeps boxes sharp when
                        # the tile is scaled up, and lets them be toggled off.
                        self.on_frame(
                            self.camera_id,
                            base64.b64encode(jpeg.tobytes()).decode(),
                            round(self.current_fps, 1),
                            [d.model_dump() for d in detections],
                        )

            if hazards:
                now = time.time()
                if now - self._last_alert_time >= self.cooldown_seconds:
                    self._last_alert_time = now
                    top = max(hazards, key=lambda d: d.confidence)
                    # Annotated: the snapshot is the evidence an operator judges
                    # a true or false alarm on, so it must show what triggered it.
                    ok, jpeg = cv2.imencode(".jpg", annotate(frame, hazards),
                                            [cv2.IMWRITE_JPEG_QUALITY, 70])
                    frame_b64 = base64.b64encode(jpeg.tobytes()).decode() if ok else None
                    self.on_event({
                        "camera_id": self.camera_id,
                        "camera_name": self.camera_name,
                        "hazard_type": top.label,
                        "confidence": float(top.confidence),
                        "zone": self.zone,
                        "frame_b64": frame_b64,
                    })
                    logger.warning(f"HAZARD {top.label} on {self.camera_name} ({top.confidence:.0%})")

            time.sleep(0.05)

    def health(self) -> dict:
        age = self.reader.last_frame_age()
        return {
            "camera_id": self.camera_id,
            "fps": round(self.current_fps, 1),
            "inference_ms": round(self.avg_inference_ms, 1),
            "last_frame_age_s": round(age, 1) if age is not None else None,
            "online": age is not None and age < OFFLINE_THRESHOLD_SECONDS,
        }
