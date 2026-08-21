"""Run one image through the FiremeX detector from the command line.

    python ml/demo_image.py path/to/photo.jpg
    python ml/demo_image.py photo.jpg --conf 0.25      # lower the YOLO bar
    python ml/demo_image.py photo.jpg --yolo-only      # learned model, nothing else

Written for showing the system without the dashboard. `ml/demo_pipeline.py`
prints the merged result; this prints WHICH BRANCH produced each box, because
the detector is a hybrid and "the model found it" and "a colour rule found it"
are very different claims to make in front of an examiner.

Branches, in the order detect() runs them (backend/app/detection/detector.py):

  1. YOLOv8            fire, smoke              LEARNED — trained on labelled CCTV
  2. HSV orange/red    fire                     rule
  3. HSV blue/green    gas_fire, lpg_fire, chemical_fire   rule, NO training data
  4. Optical flow      gas_shimmer              rule, needs consecutive frames
  5. Box geometry      person_down              rule, on a YOLO person box

Everything then passes through one IoU de-duplication stage, so the merged
output is what a camera pipeline would actually act on.
"""
import argparse
import hashlib
import os
import subprocess
import sys
import time
import warnings

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import cv2                                              # noqa: E402
from app.detection.detector import HazardDetector       # noqa: E402

DEFAULT_MODEL = os.path.join(BACKEND, "models", "fire_model.pt")

# (attribute on HazardDetector, short name, what it is, BGR colour)
# Colours are per BRANCH rather than per label — the point of this script is
# the mechanism, not the hazard class.
BRANCHES = [
    ("_yolo_detect",       "YOLOv8",       "LEARNED  — trained on labelled CCTV",     (0,   0, 255)),
    ("_colour_fire_detect", "HSV fire",    "rule     — orange/red flame colour",      (0, 140, 255)),
    ("_gas_colour_detect",  "HSV gas",     "rule     — blue/green flame, NO training data", (255, 140, 0)),
    ("_gas_shimmer_detect", "Optical flow", "rule     — heat shimmer (needs video)",  (0, 215, 255)),
    ("_person_down_detect", "Geometry",    "rule     — collapsed-person aspect ratio", (200, 0, 200)),
]


def rule(title=""):
    print(f"\n\033[1m{title}\033[0m" if title else "")
    print("─" * 72)


def model_card(path, detector, device_note):
    """What weights are actually loaded. Shown first because the single most
    common question is 'is that really your model, or a stock one?'"""
    size_mb = os.path.getsize(path) / 1e6
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()[:16]
    params = sum(p.numel() for p in detector.model.model.parameters())

    rule("MODEL")
    print(f"  weights     : {os.path.relpath(path, ROOT)}")
    print(f"  size        : {size_mb:.1f} MB     sha256: {digest}…")
    print(f"  parameters  : {params:,}")
    print(f"  classes     : {detector.model.names}")
    print(f"  device      : {device_note}")
    print(f"  YOLO conf   : {detector.threshold:.2f}  (boxes below this are dropped)")


def main():
    ap = argparse.ArgumentParser(description="Run one image through the FiremeX hybrid detector.")
    ap.add_argument("image", help="path to an image file")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="weights (.pt)")
    ap.add_argument("--conf", type=float, default=0.50,
                    help="YOLO confidence threshold (default 0.50, the product default)")
    ap.add_argument("--yolo-only", action="store_true",
                    help="run only the learned branch — no colour/flow/geometry rules")
    ap.add_argument("--save", default=os.path.join(ROOT, "ml", "demo_output.jpg"),
                    help="where to write the annotated image")
    ap.add_argument("--no-open", action="store_true", help="don't open the result in Preview")
    args = ap.parse_args()

    img_path = args.image if os.path.isabs(args.image) else os.path.join(os.getcwd(), args.image)
    frame = cv2.imread(img_path)
    if frame is None:
        raise SystemExit(f"Could not read image: {img_path}")

    if not os.path.exists(args.model):
        raise SystemExit(f"Weights not found: {args.model}")

    print(f"\nLoading detector from {os.path.relpath(args.model, ROOT)} …\n")
    # Both arguments are passed explicitly so the detector never reaches for
    # the cloud's settings module (same contract the edge agent uses).
    detector = HazardDetector(model_path=args.model, threshold=args.conf)

    import torch
    device = "mps (Apple GPU)" if torch.backends.mps.is_available() else "cpu"
    model_card(args.model, detector, device)

    h, w = frame.shape[:2]
    rule("INPUT")
    print(f"  file        : {os.path.basename(img_path)}")
    print(f"  resolution  : {w} × {h}")

    branches = BRANCHES[:1] if args.yolo_only else BRANCHES

    rule("DETECTION — BY BRANCH")
    attributed = []          # (box, branch_name, colour)
    t0 = time.time()
    for attr, name, what, colour in branches:
        boxes = getattr(detector, attr)(frame)
        print(f"\n  {name:13} {what}")
        if not boxes:
            note = ""
            if attr == "_gas_shimmer_detect":
                note = "   (expected — optical flow needs two consecutive frames)"
            print(f"    → nothing{note}")
        for b in boxes:
            print(f"    → {b.label:14} {b.confidence:.0%}   "
                  f"box=({int(b.x1)},{int(b.y1)})-({int(b.x2)},{int(b.y2)})")
            attributed.append((b, name, colour))
    elapsed_ms = (time.time() - t0) * 1000

    # detect() is exactly: run every branch, then de-duplicate. Re-using the
    # detector's own _deduplicate keeps this identical to production rather
    # than a demo-only approximation.
    merged = detector._deduplicate([b for b, _, _ in attributed])
    hazards = detector.is_hazard(merged)

    rule("MERGED (after IoU de-duplication, > 0.4 overlap)")
    print(f"  raw boxes {len(attributed)}  →  {len(merged)} after de-duplication")
    for b in merged:
        src = next((n for bb, n, _ in attributed if bb is b), "?")
        print(f"    {b.label:14} {b.confidence:.0%}   from {src}")

    rule("WHAT THE SYSTEM WOULD DO")
    if hazards:
        top = max(hazards, key=lambda d: d.confidence)
        print(f"  ALERT RAISED  →  {top.label.upper()} at {top.confidence:.0%}")
        print(f"  • annotated snapshot attached as evidence")
        print(f"  • 30 s cooldown before this camera can alert again")
        print(f"  • sirens / fire brigade are NOT called yet — an operator must")
        print(f"    promote it to an incident first (human-in-the-loop gate)")
    else:
        print("  No hazard — nothing is raised.")
    print(f"\n  inference   : {elapsed_ms:.0f} ms on {device}")

    # Draw. Boxes are coloured by the branch that found them, so the picture
    # carries the same attribution as the text above.
    out = frame.copy()
    for b, name, colour in attributed:
        keep = any(m is b for m in merged)
        x1, y1, x2, y2 = int(b.x1), int(b.y1), int(b.x2), int(b.y2)
        # De-duplicated-away boxes are drawn thin, so the overlap the IoU stage
        # removed is visible rather than silently absent.
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2 if keep else 1)
        if not keep:
            continue
        label = f"{name}: {b.label} {b.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        top = max(y1, th + 6)
        cv2.rectangle(out, (x1, top - th - 6), (x1 + tw + 6, top), colour, -1)
        cv2.putText(out, label, (x1 + 3, top - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # Legend, so the colours are readable without the terminal alongside.
    y = 20
    for _, name, _what, colour in branches:
        cv2.rectangle(out, (10, y - 10), (26, y + 2), colour, -1)
        cv2.putText(out, name, (32, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)
        y += 20

    cv2.imwrite(args.save, out)
    rule("OUTPUT")
    print(f"  annotated image → {os.path.relpath(args.save, ROOT)}\n")

    if not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", args.save], check=False)


if __name__ == "__main__":
    main()
