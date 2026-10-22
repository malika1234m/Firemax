"""Which detections may raise an alert, and how loudly the free tier says so."""
import logging

import numpy as np

from app.detection.detector import HazardDetector
from app.models import DetectionBox
from ha_agent import main


def _box(label, source="model", conf=0.6):
    return DetectionBox(x1=0, y1=0, x2=10, y2=10, label=label, confidence=conf, source=source)


class _Inner:
    def __init__(self, boxes):
        self.boxes = boxes

    def detect(self, frame):
        return self.boxes

    def is_hazard(self, detections):
        return detections


def test_colour_rule_boxes_are_tagged_with_their_source():
    detector = object.__new__(HazardDetector)          # no model needed for the colour rule
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[40:160, 40:160] = (0, 120, 255)                # bright orange in BGR
    boxes = detector._colour_fire_detect(frame)
    assert boxes and all(b.label == "fire" and b.source == "colour" for b in boxes)


def test_colour_rule_fire_does_not_alert_on_learned_classes_only():
    model_fire, colour_fire = _box("fire"), _box("fire", source="colour")
    f = main.ClassFilteredDetector(_Inner([model_fire, colour_fire]), ["fire", "smoke", "flame"])
    assert f.is_hazard(f.detect(None)) == [model_fire]


def test_colour_rule_fire_alerts_when_opted_in():
    colour_fire = _box("fire", source="colour")
    f = main.ClassFilteredDetector(_Inner([colour_fire]), ["fire", "colour_fire"])
    assert f.is_hazard(f.detect(None)) == [colour_fire]


def test_free_tier_warning_is_logged_once_not_every_discovery(caplog):
    main._last_limit_notice = None
    cams = {"camera.a": "A", "camera.b": "B"}
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert list(main._apply_camera_limit(cams, 1)) == ["camera.a"]
    assert sum("FREE TIER" in r.message for r in caplog.records) == 1


def test_free_tier_warning_repeats_when_the_unwatched_set_changes(caplog):
    main._last_limit_notice = None
    with caplog.at_level(logging.WARNING):
        main._apply_camera_limit({"camera.a": "A", "camera.b": "B"}, 1)
        main._apply_camera_limit({"camera.a": "A", "camera.b": "B", "camera.c": "C"}, 1)
    assert sum("FREE TIER" in r.message for r in caplog.records) == 2
