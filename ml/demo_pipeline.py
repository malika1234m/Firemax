"""Show the hybrid detection pipeline in one command.

    python ml/demo_pipeline.py                 # synthetic frames, one per branch
    python ml/demo_pipeline.py photo.jpg       # a real image

Demonstrates the Week 4 architecture: a LEARNED model for fire/smoke, where
labelled data exists, and DETERMINISTIC colour rules for the gas classes,
where it does not — all emitting the same DetectionBox contract and passing
through one IoU de-duplication stage.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(os.path.join(ROOT, "backend"))

import cv2                      # noqa: E402
import numpy as np              # noqa: E402
from app.detection.detector import HazardDetector  # noqa: E402

# Which branch each label can only have come from — the point of the demo.
ORIGIN = {
    "fire":          "YOLO (learned)  or  HSV colour rule",
    "smoke":         "YOLO (learned)",
    "flame":         "YOLO (learned)",
    "gas_fire":      "HSV colour rule — NO training data",
    "lpg_fire":      "HSV colour rule — NO training data",
    "chemical_fire": "HSV colour rule — NO training data",
    "gas_shimmer":   "optical flow — NO training data",
    "person_down":   "geometry on YOLO person box",
}


def report(detector, frame, title):
    boxes = detector.detect(frame)
    hazards = detector.is_hazard(boxes)
    print(f"\n{title}")
    print(f"  detect() -> {len(boxes)} box(es) after IoU de-duplication")
    for b in boxes:
        print(f"    {b.label:14} conf={b.confidence:.2f}   [{ORIGIN.get(b.label, 'other')}]")
    print(f"  is_hazard() -> would raise an alert for: {[h.label for h in hazards] or 'nothing'}")


def synthetic(colour_bgr):
    img = np.full((480, 640, 3), (20, 18, 16), np.uint8)
    cv2.circle(img, (320, 240), 90, colour_bgr, -1)
    return img


def main():
    print("Loading detector …")
    d = HazardDetector()

    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.isabs(path):
            path = os.path.join(ROOT, path)
        img = cv2.imread(path)
        if img is None:
            raise SystemExit(f"Could not read image: {path}")
        report(d, img, f"REAL IMAGE — {os.path.basename(path)}")
        out = os.path.join(ROOT, "ml", "demo_output.jpg")
        for b in d.detect(img):
            cv2.rectangle(img, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), (0, 0, 255), 2)
            cv2.putText(img, f"{b.label} {b.confidence:.0%}", (int(b.x1), int(b.y1) - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.imwrite(out, img)
        print(f"\n  annotated image written to ml/demo_output.jpg")
        return

    report(d, synthetic((30, 120, 245)), "ORANGE flame  — ordinary fire")
    report(d, synthetic((250, 170, 40)), "BLUE flame    — natural gas / LPG")
    report(d, synthetic((60, 220, 60)),  "GREEN flame   — chemical / copper")
    print("\nThe blue and green hazards are detected with NO training data,")
    print("from combustion chemistry — the Week 4 hybrid argument.")


if __name__ == "__main__":
    main()
