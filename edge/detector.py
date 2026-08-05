"""Pluggable detector for the edge agent.

- "yolo": reuses the shared FiremeX HazardDetector (same model/logic as the
  cloud used to run). Requires the detection package + model on the box.
- "mock": no ML dependencies at all — never reports a hazard. Handy for
  wiring up a new site, low-power hardware during setup, and tests.
"""
import logging

logger = logging.getLogger("edge.detector")


class MockDetector:
    def detect(self, frame):
        return []

    def is_hazard(self, detections):
        return []


def build_detector(mode: str):
    if mode == "yolo":
        # Imported lazily so mock mode / self-test need none of the ML stack.
        from app.detection.detector import HazardDetector
        logger.info("Detector: YOLO (real model)")
        return HazardDetector()
    logger.info("Detector: mock (no ML) — set DETECTOR_MODE=yolo for real detection")
    return MockDetector()
