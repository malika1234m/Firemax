"""Fine-tune YOLOv8 on the FiremeX fire/smoke dataset.

Produces everything a supervisor or examiner asks to see:
  runs/detect/<name>/results.csv          per-epoch loss and metrics
  runs/detect/<name>/results.png          training curves
  runs/detect/<name>/confusion_matrix.png where the model confuses classes
  runs/detect/<name>/PR_curve.png         precision/recall trade-off
  runs/detect/<name>/val_batch*.jpg       predictions vs ground truth
  runs/detect/<name>/weights/best.pt      the trained model

Usage:
    python ml/train.py --data ml/data.yaml --epochs 40
    python ml/train.py --data ml/data.yaml --epochs 5 --quick   # smoke test first
    python ml/train.py --resume                                 # after a crash

Long runs on a laptop get interrupted. Ultralytics writes weights/last.pt after
every epoch, carrying the optimizer and EMA state, so --resume picks the run up
at the next epoch with the learning-rate schedule intact rather than restarting.
Wrap long runs in `caffeinate -dimsu` — a laptop that sleeps mid-run suspends
training, and waking is where these runs tend to die.

Run --quick once before committing to a long run. It trains for a couple of
minutes and proves the dataset paths, labels and classes are wired correctly;
discovering a broken data.yaml four hours into a real run is a bad evening.
"""
import argparse
import platform
from pathlib import Path

import numpy as np

# ultralytics 8.2.0 computes average precision with np.trapz, which NumPy 2.0
# removed in favour of the identically-behaving np.trapezoid. Both versions are
# pinned deliberately (see backend/requirements.txt — ultralytics 8.2.0 is held
# back because later releases changed torch.load's weights_only default), so
# this alias is the smallest fix that keeps both pins intact. Without it,
# training completes but every validation run dies before writing metrics.
if not hasattr(np, "trapz"):
    np.trapz = np.trapezoid


def pick_device() -> str:
    """Apple Silicon exposes its GPU as 'mps', which is several times faster
    than CPU for this model size. CUDA if present, else CPU."""
    import torch
    if torch.cuda.is_available():
        return "0"
    if platform.system() == "Darwin" and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def resume(args):
    """Continue an interrupted run from its last checkpoint.

    Every hyperparameter is read back out of the checkpoint by ultralytics, so
    nothing here re-specifies epochs, augmentation or device — passing them
    alongside resume=True is how people accidentally restart at epoch 0 with a
    fresh optimizer. Results append to the original runs/detect/<name>/.
    """
    ckpt = Path(args.resume or f"runs/detect/{args.name}/weights/last.pt")
    if not ckpt.exists():
        raise SystemExit(
            f"{ckpt} not found — nothing to resume. Check runs/detect/ for the "
            "run you meant, or start fresh without --resume."
        )

    import torch
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    done = state.get("epoch", -1) + 1        # stored 0-indexed, -1 once finished
    total = (state.get("train_args") or {}).get("epochs", "?")
    if done <= 0:
        raise SystemExit(
            f"{ckpt} is a finished run (no epochs left to resume). Use it as "
            "--model to fine-tune further, or start a new run."
        )
    print(f"[train] resuming {ckpt} at epoch {done + 1}/{total}")

    from ultralytics import YOLO
    YOLO(str(ckpt)).train(resume=True)
    print(f"[train] artefacts in {ckpt.parent.parent}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="ml/data.yaml", help="dataset YAML")
    ap.add_argument("--model", default="yolov8n.pt",
                    help="starting weights. Fine-tuning from COCO-pretrained "
                         "converges far faster than training from scratch on a small set.")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--name", default="firemex_v1")
    ap.add_argument("--quick", action="store_true",
                    help="2 epochs at 320px — wiring check, not a real run")
    ap.add_argument("--resume", nargs="?", const="", metavar="CHECKPOINT",
                    help="continue an interrupted run from its last.pt. Defaults to "
                         "runs/detect/<name>/weights/last.pt; pass a path to override.")
    args = ap.parse_args()

    if args.resume is not None:
        return resume(args)

    if not Path(args.data).exists():
        raise SystemExit(
            f"{args.data} not found. Copy ml/data.yaml.example to ml/data.yaml and "
            "point it at your dataset — see ml/README.md."
        )

    if args.quick:
        args.epochs, args.imgsz, args.name = 2, 320, args.name + "_quick"

    device = pick_device()
    print(f"[train] device={device}  epochs={args.epochs}  imgsz={args.imgsz}  batch={args.batch}")

    from ultralytics import YOLO
    model = YOLO(args.model)

    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        name=args.name,
        patience=10,          # stop early if validation stops improving
        seed=0,               # reproducible — an examiner may ask
        val=True,
        plots=True,           # emits the curves and confusion matrix
        # Hue jitter is deliberately near-zero: hazard classes here are
        # separated by FLAME COLOUR (blue gas vs orange fire vs green
        # chemical). Shifting hue during augmentation would destroy exactly
        # the signal the deterministic branches rely on.
        hsv_h=0.005,
        hsv_s=0.6,
        hsv_v=0.4,
        fliplr=0.5,
        flipud=0.0,           # fire does not appear upside down on CCTV
        degrees=5.0,
        translate=0.1,
        scale=0.4,
        mosaic=1.0,
    )

    metrics = model.val(data=args.data, device=device)
    print("\n[train] final validation")
    print(f"  mAP50    : {metrics.box.map50:.3f}")
    print(f"  mAP50-95 : {metrics.box.map:.3f}")
    print(f"  precision: {metrics.box.mp:.3f}")
    print(f"  recall   : {metrics.box.mr:.3f}   <- prioritised for life safety")
    print(f"\n[train] artefacts in runs/detect/{args.name}/")
    print(f"[train] trained weights: runs/detect/{args.name}/weights/best.pt")
    print("[train] to use it in the app, copy to backend/models/fire_model.pt")


if __name__ == "__main__":
    main()
