"""Build a train/valid/test split from ml/datasets/raw/ — grouped by source.

This implements the Week 7 finding. The dataset contains 48 scene groups of 5
near-identical frames each (`fire_detected_var10_img1..5`). A random per-image
split would put frames 1,3,5 of a scene in train and 2,4 in validation — the
model would then be scored on pictures it had effectively memorised, reporting
an accuracy that would evaporate in a real building.

Splitting by GROUP means every frame of a scene lands in exactly one split, so
validation measures generalisation to unseen scenes. The split is stratified
across fire/smoke scenes so both appear in every split, and seeded so it is
reproducible.

    python ml/split_dataset.py
"""
import os
import random
import shutil
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "datasets", "raw")
OUT = os.path.join(HERE, "datasets", "fire")
SEED = 0
RATIOS = {"train": 0.70, "valid": 0.20, "test": 0.10}


def group_of(filename: str) -> str:
    """'fire_detected_var10_img3.png' -> 'fire_detected_var10' (the scene)."""
    stem = os.path.splitext(filename)[0]
    return stem.rsplit("_img", 1)[0] if "_img" in stem else stem


def main():
    images = sorted(f for f in os.listdir(os.path.join(RAW, "images")) if f.endswith(".png"))

    groups = defaultdict(list)
    skipped = []
    for img in images:
        label = os.path.splitext(img)[0] + ".txt"
        if not os.path.exists(os.path.join(RAW, "labels", label)):
            # An unlabelled hazard image would teach the model that fire is
            # background. Excluded rather than silently treated as a negative.
            skipped.append(img)
            continue
        groups[group_of(img)].append(img)

    # Stratify: split fire scenes and smoke scenes separately, so a small
    # dataset can't accidentally put every smoke scene in one split.
    by_kind = defaultdict(list)
    for g in groups:
        by_kind[g.split("_")[0]].append(g)

    rng = random.Random(SEED)
    assign = {}
    for kind, gs in by_kind.items():
        gs = sorted(gs)
        rng.shuffle(gs)
        n = len(gs)
        n_train = round(n * RATIOS["train"])
        n_valid = round(n * RATIOS["valid"])
        for i, g in enumerate(gs):
            assign[g] = "train" if i < n_train else "valid" if i < n_train + n_valid else "test"

    for split in RATIOS:
        for sub in ("images", "labels"):
            d = os.path.join(OUT, split, sub)
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d, exist_ok=True)

    counts = defaultdict(lambda: {"images": 0, "groups": 0, "boxes": 0})
    for g, imgs in groups.items():
        split = assign[g]
        counts[split]["groups"] += 1
        for img in imgs:
            stem = os.path.splitext(img)[0]
            shutil.copy2(os.path.join(RAW, "images", img),
                         os.path.join(OUT, split, "images", img))
            src_lbl = os.path.join(RAW, "labels", stem + ".txt")
            dst_lbl = os.path.join(OUT, split, "labels", stem + ".txt")
            shutil.copy2(src_lbl, dst_lbl)
            counts[split]["images"] += 1
            counts[split]["boxes"] += len([l for l in open(src_lbl).read().split("\n") if l.strip()])

    print(f"[split] {len(groups)} scene groups, seed={SEED}")
    for split in ("train", "valid", "test"):
        c = counts[split]
        print(f"  {split:6} {c['groups']:3} groups  {c['images']:4} images  {c['boxes']:4} boxes")
    if skipped:
        print(f"[split] skipped {len(skipped)} unlabelled image(s): {', '.join(skipped[:3])}")

    # Prove the property that matters: no scene appears in two splits.
    seen = {}
    leaks = []
    for split in ("train", "valid", "test"):
        for img in os.listdir(os.path.join(OUT, split, "images")):
            g = group_of(img)
            if g in seen and seen[g] != split:
                leaks.append((g, seen[g], split))
            seen[g] = split
    print(f"[split] cross-split scene leakage: {len(leaks)} (0 = correct)")


if __name__ == "__main__":
    main()
