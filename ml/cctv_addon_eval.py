"""Run the Home Assistant add-on's OWN detector over recorded CCTV clips.

Not a model benchmark: the detector is built with ha_agent.main.build_detector()
from the add-on's default options, so every branch the add-on runs (YOLO, colour
rule, gas colour, optical flow, person-down) runs here too, and alerts are
decided exactly as EdgePipeline decides them (hazard classes filtered, then
confidence >= confidence_threshold, then the per-camera cooldown).

Every decoded frame is checked, then the add-on's real sampling is replayed on
top: one frame per 1/process_fps seconds of video, cooldown applied, to give the
alert times a user would actually have seen.

    PYTHONPATH=edge:backend:. python ml/cctv_addon_eval.py \
        --model release-assets/model-v5/fire_model.pt \
        --out reports/ha_audit ml/datasets/own_camera/*/take3_02.mp4 ...

Ground truth, where given (--truth clip=start-end,...), is in FRAME numbers and
comes from ml/build_own_dataset.py's hand-reviewed REVIEWED ranges.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "edge", ROOT / "backend"):
    sys.path.insert(0, str(p))

from ha_agent import main as addon            # noqa: E402
from ha_agent import options as addon_opts    # noqa: E402
from pipeline import annotate                 # noqa: E402


def fourcc(cap) -> str:
    v = int(cap.get(cv2.CAP_PROP_FOURCC))
    return "".join(chr((v >> 8 * i) & 0xFF) for i in range(4)).strip("\x00") or "?"


def parse_truth(items):
    truth = {}
    for item in items or []:
        clip, ranges = item.split("=", 1)
        truth[clip] = [tuple(int(x) for x in r.split("-")) for r in ranges.split(",") if r]
    return truth


def in_ranges(i, ranges):
    return any(a <= i <= b for a, b in ranges)


def evaluate(path: str, detector, opts, out_dir: Path, truth, annotate_video: bool):
    proc = psutil.Process()
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"clip": path, "error": "could not open"}
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    declared = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    codec = fourcc(cap)
    name = Path(path).name

    writer = None
    if annotate_video:
        out_dir.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(out_dir / f"{Path(path).stem}_annotated.mp4"),
                                 cv2.VideoWriter_fourcc(*"mp4v"), fps or 15, (960, 540))

    rows, infer_ms, rss = [], [], []
    proc.cpu_percent(None)
    t_start = time.time()
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        dets = detector.detect(frame)
        hazards = [d for d in detector.is_hazard(dets) if d.confidence >= opts.confidence_threshold]
        infer_ms.append((time.perf_counter() - t0) * 1000)
        learned = {}
        for d in dets:
            if d.source == "model":
                learned[d.label] = max(learned.get(d.label, 0.0), round(d.confidence, 3))
        rows.append({
            "i": i, "t": round(i / fps, 3) if fps else None,
            "hazards": [(d.label, round(d.confidence, 3)) for d in hazards],
            "learned": learned,
            "other": sorted({d.label for d in dets if d.source != "model" or d.label not in learned}),
        })
        if writer is not None:
            vis = annotate(frame, [d for d in dets if d.source == "model"])
            tag = f"{name}  t={i / fps:5.2f}s  frame {i}"
            if hazards:
                top = max(hazards, key=lambda d: d.confidence)
                tag += f"  ALERT-LEVEL {top.label} {top.confidence:.0%}"
            cv2.putText(vis, tag, (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 5, cv2.LINE_AA)
            cv2.putText(vis, tag, (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2, cv2.LINE_AA)
            writer.write(cv2.resize(vis, (960, 540)))
        if i % 25 == 0:
            rss.append(proc.memory_info().rss / 1e6)
        i += 1
    wall = time.time() - t_start
    cpu = proc.cpu_percent(None)
    cap.release()
    if writer is not None:
        writer.release()

    positive = [r for r in rows if r["hazards"]]
    by_label = {}
    for r in positive:
        for label, _ in r["hazards"]:
            by_label[label] = by_label.get(label, 0) + 1
    confs = [c for r in positive for _, c in r["hazards"]]
    # Flicker: positive→negative→positive changes, a measure of frame-to-frame consistency.
    flips = sum(1 for a, b in zip(rows, rows[1:]) if bool(a["hazards"]) != bool(b["hazards"]))

    # The add-on's own view: one frame per 1/process_fps s, then the cooldown.
    step = max(1, round(fps / opts.process_fps)) if fps else 1
    sampled = rows[::step]
    alerts, last = [], -1e9
    for r in sampled:
        if r["hazards"] and r["t"] - last >= opts.alert_cooldown_seconds:
            last = r["t"]
            top = max(r["hazards"], key=lambda x: x[1])
            alerts.append({"t": r["t"], "frame": r["i"], "label": top[0], "confidence": top[1]})

    result = {
        "clip": name, "path": path, "codec": codec, "width": w, "height": h,
        "fps": round(fps, 2), "declared_frames": declared, "decoded_frames": len(rows),
        "duration_s": round(len(rows) / fps, 2) if fps else None,
        "frames_with_hazard": len(positive), "hazard_frames_by_label": by_label,
        "first_hazard": ({"t": positive[0]["t"], "frame": positive[0]["i"],
                          "hazards": positive[0]["hazards"]} if positive else None),
        "confidence": ({"min": min(confs), "median": float(np.median(confs)), "max": max(confs)}
                       if confs else None),
        "flicker_transitions": flips,
        "learned_max": {lab: max(r["learned"].get(lab, 0) for r in rows)
                        for lab in sorted({k for r in rows for k in r["learned"]})},
        "other_branch_labels": sorted({lab for r in rows for lab in r["other"]}),
        "infer_ms": {"mean": round(float(np.mean(infer_ms)), 1),
                     "p95": round(float(np.percentile(infer_ms, 95)), 1)},
        "processing_fps": round(len(rows) / wall, 2), "wall_s": round(wall, 1),
        "cpu_percent_avg": round(cpu, 1), "rss_mb_max": round(max(rss), 1) if rss else None,
        "rss_mb_first_last": [round(rss[0], 1), round(rss[-1], 1)] if rss else None,
        "addon_sampling": {"every_n_frames": step, "frames_checked": len(sampled),
                           "frames_with_hazard": sum(1 for r in sampled if r["hazards"]),
                           "alerts": alerts},
    }

    if name in truth:
        gt = truth[name]
        tp = sum(1 for r in rows if in_ranges(r["i"], gt) and r["hazards"])
        fn = sum(1 for r in rows if in_ranges(r["i"], gt) and not r["hazards"])
        fp = sum(1 for r in rows if not in_ranges(r["i"], gt) and r["hazards"])
        tn = sum(1 for r in rows if not in_ranges(r["i"], gt) and not r["hazards"])
        first_true = min((a for a, _ in gt), default=None)
        result["ground_truth"] = {
            "fire_frames": gt, "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "frame_recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "false_positive_frames": fp,
            "latency_s": (round((positive[0]["i"] - first_true) / fps, 2)
                          if positive and first_true is not None else None),
            "longest_missed_run_s": round(_longest_gap(rows, gt) / fps, 2) if fps else None,
        }

    (out_dir / f"{Path(path).stem}_frames.json").write_text(json.dumps(rows))
    return result


def _longest_gap(rows, gt):
    best = run = 0
    for r in rows:
        if in_ranges(r["i"], gt) and not r["hazards"]:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--model", required=True)
    ap.add_argument("--sha256", default=addon_opts.CURRENT_MODEL[1])
    ap.add_argument("--out", default="reports/ha_audit")
    ap.add_argument("--truth", nargs="*", help="clip.mp4=start-end,start-end (frames)")
    ap.add_argument("--annotate", nargs="*", default=[], help="clip names to write annotated video for")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = addon_opts.load("/nonexistent")          # the add-on's shipped defaults
    opts["model_path"] = os.path.abspath(args.model)
    opts["model_url"], opts["model_sha256"] = "", args.sha256
    proc = psutil.Process()
    rss0 = proc.memory_info().rss / 1e6
    t0 = time.time()
    detector = addon.build_detector(opts)
    startup = {"model_load_s": round(time.time() - t0, 2),
               "rss_before_mb": round(rss0, 1), "rss_after_load_mb": round(proc.memory_info().rss / 1e6, 1)}
    print(json.dumps({"startup": startup, "threshold": opts.confidence_threshold,
                      "hazard_classes": opts.hazard_classes, "process_fps": opts.process_fps,
                      "cooldown_s": opts.alert_cooldown_seconds}))

    truth = parse_truth(args.truth)
    results = []
    for clip in args.clips:
        r = evaluate(clip, detector, opts, out_dir, truth, Path(clip).name in args.annotate)
        print(json.dumps(r), flush=True)
        results.append(r)
    (out_dir / "results.json").write_text(json.dumps({"startup": startup, "results": results}, indent=2))


if __name__ == "__main__":
    main()
