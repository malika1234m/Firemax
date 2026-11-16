import importlib.util, sys, time, statistics, cv2, json
sys.path.insert(0, "backend")
from app.detection.detector import HazardDetector as New
spec = importlib.util.spec_from_file_location("old_detector", sys.argv[1]); old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
M = "release-assets/model-v5/fire_model.pt"
cap = cv2.VideoCapture("ml/datasets/own_camera/20261026_201723_take3/take3_02.mp4")
frames = []
i = 0
while len(frames) < 30:
    ok, f = cap.read()
    if not ok: break
    if i % 18 == 0: frames.append(f)
    i += 1
FIRE = {"fire", "smoke", "flame"}
def run(det):
    det.detect(frames[0])                       # warm-up
    ts, fires = [], []
    for f in frames:
        t = time.perf_counter(); boxes = det.detect(f); ts.append((time.perf_counter() - t) * 1000)
        fires.append(sorted(round(b.confidence, 3) for b in boxes if b.source == "model" and b.label in FIRE))
    return ts, fires
o_ts, o_f = run(old.HazardDetector(M, 0.5))
n_ts, n_f = run(New(M, 0.5, branches={"model"}))
print(json.dumps({"frames": len(frames),
  "old_all_branches_ms": {"mean": round(statistics.mean(o_ts)), "median": round(statistics.median(o_ts))},
  "new_addon_default_ms": {"mean": round(statistics.mean(n_ts)), "median": round(statistics.median(n_ts))},
  "speedup_mean": round(statistics.mean(o_ts) / statistics.mean(n_ts), 2),
  "frames_with_model_fire_old": sum(1 for x in o_f if x), "frames_with_model_fire_new": sum(1 for x in n_f if x),
  "frames_where_old_lost_model_fire_box_in_dedupe": sum(1 for a, b in zip(o_f, n_f) if len(a) < len(b)),
  "identical_model_boxes": sum(1 for a, b in zip(o_f, n_f) if a == b)}))
