"""Turn clips recorded with ml/record_camera.py into a YOLO dataset.

    python ml/build_own_dataset.py            # frames + draft boxes + to_label/
    python ml/build_own_dataset.py --apply corrected.zip   # take back fixed boxes

Reads ml/datasets/own_camera/clips.csv and writes ml/datasets/own/:

    own/{train,test}/images/*.jpg
    own/{train,test}/labels/*.txt      YOLO boxes, class ids as in model-v2 (0 smoke, 1 fire)
    own/to_label/                      every frame that needs a human to check its boxes
    own/review/                        contact sheets of the draft boxes
    own/data.yaml

How the boxes are made — read this before trusting them:

* Clips whose label starts with a NEGATIVE prefix (lighter_, no_) get empty
  label files. They teach the model what is NOT a fire: on this camera a
  lighter flame is a tiny over-exposed white dot, the same as a lamp.
* Every other clip gets DRAFT fire boxes from the flame's colour. This camera
  renders burning paper pink/purple rather than orange, which is also why
  model-v2 scores it low. Model-v2 itself is not used for drafts: it boxed
  fire in 2 of the ~35 burning frames, and every missed frame would have
  taught the new model that fire is background.
  The colour rule also boxes pink objects and bright paper, so every draft is
  corrected by hand (makesense.ai, see to_label/README.txt) before training.

The split is by CLIP, never by frame. Frames half a second apart are almost
identical, so a frame-level split would put copies of the training pictures in
the test set and the score would say nothing.
"""
import argparse
import csv
import os
import shutil
import zipfile

import cv2
import numpy as np

ML = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ML, "datasets", "own_camera")
OUT = os.path.join(ML, "datasets", "own")

# Same ids as model-v2 (release-assets/model-v2), which this dataset fine-tunes.
NAMES = {0: "smoke", 1: "fire"}
FIRE = 1

NEGATIVE_PREFIXES = ("lighter_", "no_")

# Hand review of the 2026-10-26 recordings (frame-index ranges, inclusive),
# decided from the contact sheets in own/review/. In a "fire" range the flame
# pixels in the lower part of the picture become ONE box around the bowl; the
# pink bag hanging above it is the same colour and is never inside that part.
# "drop" frames are left out (corrupted, motion-blurred, fire half out of view
# or only just being lit). Every other frame of a reviewed clip has no fire.
REVIEWED = {
    "take2_01.mp4": {"fire": [], "drop": [(462, 99999)]},
    "take3_01.mp4": {"fire": [(231, 594)], "drop": [(198, 220), (363, 374)]},
    "take3_02.mp4": {"fire": [(0, 99999)], "drop": [(99, 121)]},
    "take3_03.mp4": {"fire": [(0, 99)], "drop": [(110, 121)]},
}
FIRE_REGION_TOP = 0.4        # fire boxes only from flame below 40% of the height
# Held out whole: one fire clip and one lighter clip.
DEFAULT_TEST = ("take3_02.mp4", "lighter_1m_03.mp4")
MIN_FLAME_AREA = 1500        # pixels, at 1920x1080


def frames(path, every_s, fps):
    """Yield (index, frame) every `every_s` seconds, skipping near-duplicates."""
    step = max(1, round(every_s * fps))
    cap = cv2.VideoCapture(path)
    prev, i = None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 36)).astype(np.float32)
            if prev is None or np.abs(small - prev).mean() >= 2.0:
                prev = small
                yield i, frame
        i += 1
    cap.release()


def flame_boxes(frame):
    """Draft fire boxes from this camera's burning-paper colour (YOLO lines).

    Pink/purple only: orange matched concrete lit by the fire. A box must also
    hold a near-white core (flames saturate the sensor; lit walls and the pink
    bag do not), and must not sit in the top strip, where the bag hangs.
    """
    h, s, v = cv2.split(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV))
    flame = (v >= 200) & (s >= 50) & (h >= 125) & (h <= 175)
    core = (v >= 245) & (s <= 90)
    mask = cv2.morphologyEx(flame.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    fh, fw = frame.shape[:2]
    lines = []
    for x, y, w, bh, area in stats[1:n]:
        if area < MIN_FLAME_AREA or y + bh < 0.15 * fh:
            continue
        if core[y:y + bh, x:x + w].sum() < 0.03 * w * bh:
            continue
        lines.append(f"{FIRE} {(x + w / 2) / fw:.6f} {(y + bh / 2) / fh:.6f} {w / fw:.6f} {bh / fh:.6f}")
    return lines


def in_ranges(idx, ranges):
    return any(a <= idx <= b for a, b in ranges)


def reviewed_label(clip_name, idx, frame):
    """Lines for a hand-reviewed clip: None = leave the frame out."""
    review = REVIEWED[clip_name]
    if in_ranges(idx, review["drop"]):
        return None
    if not in_ranges(idx, review["fire"]):
        return []
    fh, fw = frame.shape[:2]
    boxes = []
    for line in flame_boxes(frame):
        _, x, y, w, h = (float(v) for v in line.split())
        if y >= FIRE_REGION_TOP:
            boxes.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    if not boxes:
        return None          # fire was there but the colour rule found none: unsure
    x1, y1 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x2, y2 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    return [f"{FIRE} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"]


def review_sheet(items, path):
    """Grid of labelled frames with their boxes drawn, for a human to check."""
    tiles = []
    for img_path, lines in items:
        img = cv2.imread(img_path)
        h, w = img.shape[:2]
        for line in lines:
            c, x, y, bw, bh = line.split()
            x, y, bw, bh = float(x) * w, float(y) * h, float(bw) * w, float(bh) * h
            colour = (0, 0, 255) if int(c) == FIRE else (255, 160, 0)
            cv2.rectangle(img, (int(x - bw / 2), int(y - bh / 2)), (int(x + bw / 2), int(y + bh / 2)), colour, 6)
        tile = cv2.resize(img, (480, 270))
        cv2.putText(tile, os.path.basename(img_path)[:-4], (6, 22), 0, 0.6, (0, 255, 0), 2)
        tiles.append(tile)
    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[r:r + 4]) for r in range(0, len(tiles), 4)]
    cv2.imwrite(path, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 70])


def build(args):
    shutil.rmtree(OUT, ignore_errors=True)
    for split in ("train", "test"):
        for kind in ("images", "labels"):
            os.makedirs(os.path.join(OUT, split, kind))
    todo = os.path.join(OUT, "to_label")
    os.makedirs(os.path.join(todo, "images"))
    os.makedirs(os.path.join(todo, "labels"))
    os.makedirs(os.path.join(OUT, "review"))

    with open(os.path.join(SRC, "clips.csv")) as fh:
        clips = list(csv.DictReader(fh))

    for clip in clips:
        path = os.path.join(SRC, clip["file"])
        if not os.path.exists(path):
            continue
        name = os.path.basename(path)
        split = "test" if name in args.test else "train"
        negative = clip["label"].startswith(NEGATIVE_PREFIXES)
        items = []
        for idx, frame in frames(path, args.every, float(clip["fps"])):
            stem = f"{name[:-4]}_{idx:05d}"
            if negative:
                lines = []
            elif name in REVIEWED:
                lines = reviewed_label(name, idx, frame)
                if lines is None:
                    continue
            else:
                lines = flame_boxes(frame)
            img_path = os.path.join(OUT, split, "images", stem + ".jpg")
            cv2.imwrite(img_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            text = "\n".join(lines) + ("\n" if lines else "")
            with open(os.path.join(OUT, split, "labels", stem + ".txt"), "w") as fh:
                fh.write(text)
            if not negative and name not in REVIEWED:
                shutil.copy(img_path, os.path.join(todo, "images"))
                with open(os.path.join(todo, "labels", stem + ".txt"), "w") as fh:
                    fh.write(text)
            items.append((img_path, lines))
        if items:
            review_sheet(items, os.path.join(OUT, "review", name[:-4] + ".jpg"))
        boxed = sum(1 for _, lines in items if lines)
        kind = "negative" if negative else ("hand-reviewed" if name in REVIEWED else "draft boxes, needs checking")
        print(f"{name:22s} {split:5s} {len(items):4d} frames  {boxed:4d} with boxes  ({kind})")

    with open(os.path.join(todo, "labels.txt"), "w") as fh:
        fh.write("".join(f"{NAMES[k]}\n" for k in sorted(NAMES)))
    with open(os.path.join(OUT, "data.yaml"), "w") as fh:
        fh.write(f"# Built by ml/build_own_dataset.py from {SRC}\n")
        fh.write(f"path: {OUT}\ntrain: train/images\nval: test/images\ntest: test/images\n")
        fh.write("names:\n" + "".join(f"  {k}: {v}\n" for k, v in NAMES.items()))
    n = len(os.listdir(os.path.join(todo, "images")))
    print(f"\n{n} frames to check in {todo}")


def apply(zip_path):
    """Copy corrected YOLO label files (a makesense.ai export) over the drafts."""
    updated = 0
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            stem = os.path.basename(member)
            if not stem.endswith(".txt") or stem == "labels.txt":
                continue
            for split in ("train", "test"):
                dest = os.path.join(OUT, split, "labels", stem)
                if os.path.exists(dest):
                    with open(dest, "wb") as fh:
                        fh.write(z.read(member))
                    updated += 1
    print(f"updated {updated} label files from {zip_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--every", type=float, default=0.5, help="seconds between frames (default 0.5)")
    ap.add_argument("--test", nargs="*", default=list(DEFAULT_TEST), help="clip files held out for testing")
    ap.add_argument("--apply", metavar="ZIP", help="take corrected labels back from a makesense.ai YOLO export")
    args = ap.parse_args()
    if args.apply:
        apply(args.apply)
    else:
        build(args)


if __name__ == "__main__":
    main()
