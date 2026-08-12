# Model training

The detector is a **hybrid**: a learned YOLOv8 model for `fire` and `smoke`,
where labelled data exists, plus deterministic HSV/optical-flow branches for
the gas classes, where it does not. This directory covers the learned half.
See `backend/app/detection/detector.py` for the rest.

## 1. Get a dataset

Any YOLO-format fire/smoke dataset works. Common sources:

- **Roboflow Universe** — search "fire smoke detection", then *Download →
  YOLOv8*. Exports in exactly the layout `data.yaml.example` expects.
- **D-Fire** — 21k annotated images, fire and smoke.

Unpack into `ml/datasets/fire/`.

> **Split by source, not by frame.** If frames from one video land in both
> train and validation, the model is scored on images it memorised and the
> reported accuracy is fiction. If your data comes from video, keep all frames
> from a given clip in the same split.

## 2. Configure

```bash
cp ml/data.yaml.example ml/data.yaml   # then edit paths/classes if needed
```

## 3. Check the wiring before a long run

```bash
cd "$(git rev-parse --show-toplevel)"
backend/.venv/bin/python ml/train.py --quick
```

Two epochs at 320px. It proves the paths, labels and class list are right.
Finding a broken `data.yaml` four hours into a real run wastes an evening.

## 4. Train

```bash
backend/.venv/bin/python ml/train.py --epochs 40
```

Uses the Apple GPU (`mps`) automatically. Rough guide on an M-series laptop:
~2k images at 640px is a few minutes per epoch, so 40 epochs is an overnight
job. Cut `--epochs`, `--imgsz 416`, or the dataset size if you need it sooner.

## 5. What you get

Everything lands in `runs/detect/firemex_v1/`:

| File | Shows |
|---|---|
| `results.csv` | per-epoch losses and metrics — the raw evidence |
| `results.png` | training curves; check val loss isn't diverging |
| `confusion_matrix.png` | which classes get confused (expect smoke↔fire) |
| `PR_curve.png` | the precision/recall trade-off |
| `val_batch*_pred.jpg` | predictions next to ground truth |
| `weights/best.pt` | the trained model |

## 6. Use it in the app

```bash
cp runs/detect/firemex_v1/weights/best.pt backend/models/fire_model.pt
```

The pipeline picks it up on restart — `MODEL_PATH` in `backend/.env`.

## Reading the numbers honestly

**Recall matters more than precision here.** A missed fire is a catastrophe; a
false alarm is an annoyance an operator dismisses in one click. When tuning the
confidence threshold, favour recall — and say so, because it is a policy
decision about which failure the customer can live with, not a purely technical
one.

A first run on a small public dataset typically lands around mAP50 0.5–0.7.
That is a normal starting point, not a failure. The curves and the confusion
matrix are what show you understand the model — the single mAP number is the
least interesting thing in the folder.
