"""Compare two fire models on held-out clips, the way the add-on uses them.

    python ml/compare_models.py OLD.pt NEW.pt CLIP:fire CLIP:none ...

Each clip is tagged with what it really shows:
  fire  — a fire is visible the whole time: the share of frames scored
          fire >= threshold is the catch rate (higher is better)
  none  — nothing is burning: every frame scored fire or smoke >= threshold
          is a false alarm (lower is better)

Frames are run one by one at the add-on's threshold, on CPU — MPS truncates
NMS (see ml/README.md) and would understate both models.
"""
import argparse
import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import cv2  # noqa: E402


def score(model, path, every, threshold):
    names = model.names
    cap = cv2.VideoCapture(path)
    i = checked = fire = alarm = 0
    best = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % every == 0:
            checked += 1
            r = model(frame, conf=0.05, device="cpu", verbose=False)[0]
            confs = {"fire": 0.0, "smoke": 0.0}
            for c, p in zip(r.boxes.cls, r.boxes.conf):
                k = names[int(c)]
                confs[k] = max(confs.get(k, 0.0), float(p))
            best = max(best, confs["fire"])
            fire += confs["fire"] >= threshold
            alarm += max(confs.values()) >= threshold
        i += 1
    return checked, fire, alarm, best


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("clips", nargs="+", help="path:fire or path:none")
    ap.add_argument("--every", type=int, default=3, help="score every Nth frame (default 3)")
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()

    from ultralytics import YOLO
    models = {"old": YOLO(args.old), "new": YOLO(args.new)}
    print(f"threshold {args.threshold}   old={args.old}   new={args.new}\n")
    for spec in args.clips:
        path, truth = spec.rsplit(":", 1)
        print(os.path.basename(path), f"({'fire visible' if truth == 'fire' else 'no fire'})")
        for tag, model in models.items():
            n, fire, alarm, best = score(model, path, args.every, args.threshold)
            if truth == "fire":
                print(f"  {tag}: fire caught in {fire}/{n} frames ({fire / n:.0%}), best fire {best:.2f}")
            else:
                print(f"  {tag}: false alarms in {alarm}/{n} frames ({alarm / n:.0%}), best fire {best:.2f}")
        print()


if __name__ == "__main__":
    main()
