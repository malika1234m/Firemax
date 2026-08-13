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


def build_detector(mode: str, confidence_threshold: float | None = None):
    if mode == "yolo":
        # Fetch/verify the weights before loading. HazardDetector silently
        # falls back to a generic COCO model when the file is missing, which
        # would leave a site "running" while detecting no fire at all.
        from config import AgentConfig
        from model import ensure_model
        ensure_model(AgentConfig.model_path, AgentConfig.model_url, AgentConfig.model_sha256)

        # Imported lazily so mock mode / self-test need none of the ML stack.
        from app.detection.detector import HazardDetector
        logger.info("Detector: YOLO (real model)")
        # Both values are passed explicitly so the shared detector never reaches
        # for the cloud's settings module, which isn't installed here.
        return HazardDetector(model_path=AgentConfig.model_path,
                              threshold=confidence_threshold)
    logger.info("Detector: mock (no ML) — set DETECTOR_MODE=yolo for real detection")
    return MockDetector()
