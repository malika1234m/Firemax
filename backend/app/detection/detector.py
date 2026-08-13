import os
import cv2
import numpy as np
from ultralytics import YOLO
from app.models import DetectionBox

# NOTE: app.config is deliberately NOT imported at module level. This module is
# shared with the edge agent, which ships without the cloud's settings machinery
# (pydantic-settings) and has no business carrying the cloud's Mongo/Stripe/
# Twilio configuration onto a customer's machine. Callers pass what they need;
# the cloud's settings are read lazily only when they don't.
DEFAULT_CONFIDENCE_THRESHOLD = 0.50

# ── Hazard labels ──────────────────────────────────────────────────────────
YOLO_HAZARD_LABELS  = {"fire", "smoke", "flame", "gas_shimmer", "person_down"}
GAS_HAZARD_LABELS   = {"gas_fire", "lpg_fire", "chemical_fire"}
ALL_HAZARD_LABELS   = YOLO_HAZARD_LABELS | GAS_HAZARD_LABELS

# ── Regular fire colour (orange/red/yellow) ────────────────────────────────
FIRE_HSV_LOWER1 = np.array([0,   150, 150])
FIRE_HSV_UPPER1 = np.array([25,  255, 255])
FIRE_HSV_LOWER2 = np.array([165, 150, 150])
FIRE_HSV_UPPER2 = np.array([180, 255, 255])
MIN_FIRE_AREA   = 400
MIN_FIRE_CONF   = 0.55

# ── Gas fire colour ranges (HSV) ──────────────────────────────────────────
# Natural gas / Methane / LPG → blue flame
GAS_BLUE_LOWER  = np.array([95,  60,  80])   # blue, moderately saturated
GAS_BLUE_UPPER  = np.array([135, 255, 255])

# LPG / Propane tip → slightly purple-blue
GAS_PURPLE_LOWER = np.array([130, 40, 80])
GAS_PURPLE_UPPER = np.array([155, 220, 255])

# Alcohol / transparent gas → very pale blue (low saturation)
GAS_PALE_LOWER  = np.array([100, 20,  180])  # low sat, very bright
GAS_PALE_UPPER  = np.array([145, 90,  255])

# Chemical / copper → green flame
CHEM_GREEN_LOWER = np.array([55,  80,  80])
CHEM_GREEN_UPPER = np.array([90,  255, 255])

MIN_GAS_AREA    = 200   # gas flames can be small (e.g. stove burner)

# ── Gas shimmer settings ───────────────────────────────────────────────────
SHIMMER_FLOW_THRESHOLD   = 1.8
SHIMMER_MIN_REGION       = 3000
SHIMMER_CONFIDENCE_SCALE = 0.0004


class HazardDetector:
    """
    Multi-hazard detector — no sensors required:
      1. YOLOv8        → fire, smoke, flame (trained on real CCTV images)
      2. HSV orange/red → regular fire detection
      3. HSV blue/green → GAS fire detection by flame colour
                          • Blue  → natural gas, methane, LPG
                          • Pale  → alcohol, hydrogen
                          • Green → chemical / copper compounds
      4. Optical flow  → gas shimmer / heat distortion
      5. Pose analysis → person down (indirect CO signal)
    """

    def __init__(self, model_path: str | None = None, threshold: float | None = None):
        # Both arguments are supplied by the edge agent. Only when a caller
        # omits them (the cloud, historically) is app.config touched at all —
        # importing it on the edge raises ModuleNotFoundError, which is exactly
        # how this surfaced: the model downloaded and verified, then the agent
        # crash-looped on an import it never needed.
        if model_path is None or threshold is None:
            from app.config import settings
            model_path = model_path or settings.MODEL_PATH
            threshold = settings.CONFIDENCE_THRESHOLD if threshold is None else threshold

        if not os.path.exists(model_path):
            fallback = os.path.join(os.path.dirname(model_path), "yolov8n.pt")
            if os.path.exists(fallback):
                model_path = fallback
                print(f"[detector] Custom model not found — using {fallback}")
            else:
                model_path = "yolov8n.pt"
                print("[detector] Downloading yolov8n.pt …")

        self.model      = YOLO(model_path)
        self.threshold  = threshold if threshold is not None else DEFAULT_CONFIDENCE_THRESHOLD
        self._prev_gray = None   # previous frame for optical flow
        print(f"[detector] Loaded: {model_path}  threshold={self.threshold}")
        print(f"[detector] Gas shimmer detection: ENABLED (optical flow)")
        print(f"[detector] Person-down detection: ENABLED (pose analysis)")

    # ── Public API ─────────────────────────────────────────────────────
    def detect(self, frame: np.ndarray) -> list[DetectionBox]:
        boxes = []
        boxes.extend(self._yolo_detect(frame))
        boxes.extend(self._colour_fire_detect(frame))
        boxes.extend(self._gas_colour_detect(frame))      # ← NEW: gas by flame colour
        boxes.extend(self._gas_shimmer_detect(frame))
        boxes.extend(self._person_down_detect(frame))
        return self._deduplicate(boxes)

    def is_hazard(self, detections: list[DetectionBox]) -> list[DetectionBox]:
        return [d for d in detections if d.label.lower() in ALL_HAZARD_LABELS]

    # ── YOLO detection ─────────────────────────────────────────────────
    def _yolo_detect(self, frame: np.ndarray) -> list[DetectionBox]:
        results = self.model(frame, verbose=False)[0]
        boxes   = []
        for box in results.boxes:
            conf  = float(box.conf[0])
            if conf < self.threshold:
                continue
            label = results.names[int(box.cls[0])]
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            boxes.append(DetectionBox(
                x1=x1, y1=y1, x2=x2, y2=y2,
                label=label, confidence=conf,
            ))
        return boxes

    # ── Colour-based fire detection ────────────────────────────────────
    def _colour_fire_detect(self, frame: np.ndarray) -> list[DetectionBox]:
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Mask for fire colours (two ranges to handle hue wrap-around)
        mask1 = cv2.inRange(hsv, FIRE_HSV_LOWER1, FIRE_HSV_UPPER1)
        mask2 = cv2.inRange(hsv, FIRE_HSV_LOWER2, FIRE_HSV_UPPER2)
        mask  = cv2.bitwise_or(mask1, mask2)

        # Morphological cleanup — remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        h, w  = frame.shape[:2]
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < MIN_FIRE_AREA:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)

            # Confidence proportional to region area (larger = more confident)
            conf = float(np.clip(area / (w * h * 0.15), MIN_FIRE_CONF, 0.99))

            # Extra check: fire pixels should be bright and warm
            roi_hsv = hsv[y:y+bh, x:x+bw]
            mean_v  = float(np.mean(roi_hsv[:, :, 2]))   # Value channel
            if mean_v < 100:                               # Too dark to be fire
                continue

            boxes.append(DetectionBox(
                x1=float(x),  y1=float(y),
                x2=float(x+bw), y2=float(y+bh),
                label="fire",
                confidence=conf,
            ))
        return boxes

    # ── Gas fire colour detection ──────────────────────────────────────
    def _gas_colour_detect(self, frame: np.ndarray) -> list[DetectionBox]:
        """
        Detects gas fires by their distinctive flame colour.

        Gas type  →  Flame colour  →  HSV range
        ─────────────────────────────────────────
        Natural gas / Methane / LPG  →  Blue       →  H 95-135
        LPG purple tip               →  Blue-violet →  H 130-155
        Alcohol / Hydrogen           →  Pale blue   →  H 100-145, low S
        Chemical / Copper compounds  →  Green       →  H 55-90
        """
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, w = frame.shape[:2]
        boxes = []

        # Define each gas type with its colour range and label
        gas_ranges = [
            (GAS_BLUE_LOWER,   GAS_BLUE_UPPER,   "gas_fire",      "Natural gas/LPG (blue flame)"),
            (GAS_PURPLE_LOWER, GAS_PURPLE_UPPER,  "lpg_fire",      "LPG (purple-blue flame)"),
            (GAS_PALE_LOWER,   GAS_PALE_UPPER,    "gas_fire",      "Alcohol/Hydrogen (pale flame)"),
            (CHEM_GREEN_LOWER, CHEM_GREEN_UPPER,  "chemical_fire", "Chemical (green flame)"),
        ]

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        for lower, upper, label, _desc in gas_ranges:
            mask = cv2.inRange(hsv, lower, upper)

            # Remove noise
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < MIN_GAS_AREA:
                    continue

                x, y, bw, bh = cv2.boundingRect(cnt)

                # Brightness check — gas flames are always bright
                roi = frame[y:y+bh, x:x+bw]
                if roi.size == 0:
                    continue
                brightness = float(np.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)))
                if brightness < 60:
                    continue

                # Reject if the region is inside a large regular-fire region
                # (orange fire already covers this area)
                fire_mask = cv2.inRange(hsv,
                    np.array([0, 150, 150]), np.array([25, 255, 255]))
                fire_overlap = np.count_nonzero(fire_mask[y:y+bh, x:x+bw])
                if fire_overlap > area * 0.6:
                    continue   # mostly orange fire, not gas

                # Confidence: based on area + brightness
                conf = float(np.clip(
                    (area / (w * h * 0.08)) * (brightness / 255) * 1.2,
                    0.50, 0.95
                ))

                boxes.append(DetectionBox(
                    x1=float(x), y1=float(y),
                    x2=float(x+bw), y2=float(y+bh),
                    label=label,
                    confidence=conf,
                ))

        return boxes

    # ── Gas shimmer detection (optical flow) ──────────────────────────
    def _gas_shimmer_detect(self, frame: np.ndarray) -> list[DetectionBox]:
        """
        Detects heat distortion / air shimmer caused by gas leaks.
        Uses dense optical flow to find regions with irregular motion
        that is NOT caused by solid objects moving — characteristic of
        refractive index changes from gas/heat.

        Limitation: works best when camera is static (fixed CCTV).
        Cannot detect colourless gases directly — only their visual effect.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_gray = gray
            return []

        # Dense optical flow — detects all pixel-level motion
        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray, gray,
            None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        self._prev_gray = gray

        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        # Threshold: keep only regions with subtle, irregular motion
        # (too high = real object moving; too low = camera noise)
        shimmer_mask = ((mag > 0.4) & (mag < SHIMMER_FLOW_THRESHOLD)).astype(np.uint8) * 255

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        shimmer_mask = cv2.morphologyEx(shimmer_mask, cv2.MORPH_CLOSE, kernel)
        shimmer_mask = cv2.morphologyEx(shimmer_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(shimmer_mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < SHIMMER_MIN_REGION:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            conf = float(np.clip(area * SHIMMER_CONFIDENCE_SCALE, 0.50, 0.82))
            boxes.append(DetectionBox(
                x1=float(x), y1=float(y),
                x2=float(x + bw), y2=float(y + bh),
                label="gas_shimmer",
                confidence=conf,
            ))
        return boxes

    # ── Person-down detection (indirect CO/gas signal) ─────────────────
    def _person_down_detect(self, frame: np.ndarray) -> list[DetectionBox]:
        """
        Detects people lying down or collapsed — an indirect indicator
        of CO poisoning or toxic gas exposure.
        Uses YOLOv8 person detection + bounding box aspect ratio analysis.
        A standing person has height > width. A collapsed person has width > height.
        """
        results = self.model(frame, verbose=False)[0]
        boxes   = []
        for box in results.boxes:
            label = results.names[int(box.cls[0])]
            if label != "person":
                continue
            conf = float(box.conf[0])
            if conf < 0.45:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bw = x2 - x1
            bh = y2 - y1
            if bh < 10 or bw < 10:
                continue
            aspect = bw / bh   # > 1.0 means wider than tall → lying down
            if aspect > 1.3:   # person is horizontal — likely collapsed
                down_conf = float(np.clip(conf * aspect * 0.6, 0.50, 0.88))
                boxes.append(DetectionBox(
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    label="person_down",
                    confidence=down_conf,
                ))
        return boxes

    # ── Remove overlapping boxes from both detectors ───────────────────
    def _deduplicate(self, boxes: list[DetectionBox]) -> list[DetectionBox]:
        if not boxes:
            return boxes
        kept = []
        for b in boxes:
            overlap = False
            for k in kept:
                if self._iou(b, k) > 0.4:
                    # Keep the higher-confidence one
                    if b.confidence > k.confidence:
                        kept.remove(k)
                    else:
                        overlap = True
                    break
            if not overlap:
                kept.append(b)
        return kept

    @staticmethod
    def _iou(a: DetectionBox, b: DetectionBox) -> float:
        ix1 = max(a.x1, b.x1); iy1 = max(a.y1, b.y1)
        ix2 = min(a.x2, b.x2); iy2 = min(a.y2, b.y2)
        inter = max(0, ix2-ix1) * max(0, iy2-iy1)
        if inter == 0:
            return 0.0
        area_a = (a.x2-a.x1) * (a.y2-a.y1)
        area_b = (b.x2-b.x1) * (b.y2-b.y1)
        return inter / (area_a + area_b - inter)
