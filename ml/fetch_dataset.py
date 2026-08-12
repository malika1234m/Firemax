"""Download the CCTV fire/smoke dataset from Hugging Face into ml/datasets/raw/.

Chosen deliberately: public fire imagery is overwhelmingly outdoor daylight
wildfire shot from a distance, while this project targets indoor/industrial
CCTV at short range — the domain gap identified in Week 3. This set is
CCTV-perspective and already in YOLO format.

    python ml/fetch_dataset.py
"""
import concurrent.futures as cf
import os
import sys

import httpx

REPO = "Simuletic/CCTV-Smoke-Fire-Emergency-Detection-Dataset"
PREFIX = "CCTV_Fire_Smoke_Emergency_Detection_Dataset"
OUT = os.path.join(os.path.dirname(__file__), "datasets", "raw")
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main"


def file_list() -> list[str]:
    r = httpx.get(f"https://huggingface.co/api/datasets/{REPO}?full=true", timeout=60)
    r.raise_for_status()
    names = [s["rfilename"] for s in r.json()["siblings"]]
    return [n for n in names if n.startswith(f"{PREFIX}/images/")
            or n.startswith(f"{PREFIX}/labels/")]


def fetch(client: httpx.Client, name: str) -> bool:
    dest = os.path.join(OUT, os.path.relpath(name, PREFIX))
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        r = client.get(f"{BASE}/{name}", follow_redirects=True, timeout=90)
        r.raise_for_status()
        tmp = dest + ".part"
        with open(tmp, "wb") as fh:
            fh.write(r.content)
        os.replace(tmp, dest)
        return True
    except Exception as exc:
        print(f"  ! {name}: {exc}", file=sys.stderr)
        return False


def main():
    files = file_list()
    print(f"[fetch] {len(files)} files from {REPO}")
    os.makedirs(OUT, exist_ok=True)
    ok = 0
    with httpx.Client() as client:
        with cf.ThreadPoolExecutor(max_workers=12) as pool:
            for i, good in enumerate(pool.map(lambda n: fetch(client, n), files), 1):
                ok += bool(good)
                if i % 60 == 0:
                    print(f"  {i}/{len(files)}")
    imgs = len(os.listdir(os.path.join(OUT, "images"))) if os.path.isdir(os.path.join(OUT, "images")) else 0
    lbls = len(os.listdir(os.path.join(OUT, "labels"))) if os.path.isdir(os.path.join(OUT, "labels")) else 0
    print(f"[fetch] done: {ok}/{len(files)} files -> {OUT}")
    print(f"[fetch] {imgs} images, {lbls} labels")


if __name__ == "__main__":
    main()
