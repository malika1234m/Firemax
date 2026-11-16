"""Serve recorded CCTV clips as a camera Home Assistant can add, with scenarios.

For end-to-end tests of the add-on in a real Home Assistant: HA's "MJPEG IP
Camera" integration points at this server, and the add-on reads it through HA
exactly as it would a real camera. The scenario is switched over HTTP, so a
test can stage "no fire → fire → fire gone → fire again → camera down".

    python ml/cctv_scenario_camera.py --port 8091 \
        --clip nofire=ml/datasets/own_camera/.../lighter_1m_02.mp4 \
        --clip fire=ml/datasets/own_camera/.../take3_02.mp4

    GET /still.jpg          the current picture (what the add-on actually checks)
    GET /stream.mjpg        the same as MJPEG, for HA's live view
    GET /mode?set=fire      switch scenario (any clip name, or "down" = no answer)
    GET /log                JSON: every mode change, with time

A clip plays in real time from the moment its mode is chosen and loops. Frames
are decoded once at start-up and kept as JPEG, so serving is cheap.
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2

STATE = {"mode": None, "since": time.time()}
LOG = []
CLIPS = {}
LOCK = threading.Lock()


def load(name, path, width):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if width and f.shape[1] > width:
            f = cv2.resize(f, (width, round(f.shape[0] * width / f.shape[1])))
        frames.append(cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes())
    cap.release()
    CLIPS[name] = {"fps": fps, "frames": frames, "path": path}
    print(f"loaded {name}: {len(frames)} frames @ {fps:.1f} fps from {path}", flush=True)


def set_mode(mode):
    with LOCK:
        STATE["mode"], STATE["since"] = mode, time.time()
        LOG.append({"t": STATE["since"], "iso": time.strftime("%H:%M:%S", time.localtime(STATE["since"])),
                    "mode": mode})
    print(f"{time.strftime('%H:%M:%S')} mode -> {mode}", flush=True)


def current():
    """(jpeg, frame index) for now, or None when the camera is 'down'."""
    with LOCK:
        mode, since = STATE["mode"], STATE["since"]
    clip = CLIPS.get(mode)
    if clip is None:
        return None
    i = int((time.time() - since) * clip["fps"]) % len(clip["frames"])
    return clip["frames"][i], i


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/mode":
            mode = parse_qs(url.query).get("set", [""])[0]
            if mode not in CLIPS and mode != "down":
                return self._send(400, f"unknown mode {mode}".encode(), "text/plain")
            set_mode(mode)
            return self._send(200, mode.encode(), "text/plain")
        if url.path == "/log":
            return self._send(200, json.dumps({"state": STATE, "log": LOG}).encode(), "application/json")
        if url.path.endswith(".jpg"):
            cur = current()
            if cur is None:
                # "down": hold the request and drop it, like a camera gone off the network.
                time.sleep(3)
                self.close_connection = True
                return
            jpeg, i = cur
            return self._send(200, jpeg, "image/jpeg")
        if url.path.endswith(".mjpg"):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    cur = current()
                    if cur is None:
                        return
                    d = cur[0]
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(d)).encode() + b"\r\n\r\n" + d + b"\r\n")
                    time.sleep(0.2)
            except (BrokenPipeError, ConnectionResetError):
                return
        self._send(404, b"not found", "text/plain")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--clip", action="append", required=True, help="name=path.mp4")
    ap.add_argument("--width", type=int, default=0, help="downscale wider frames to this width")
    ap.add_argument("--start", default=None, help="initial mode (default: first clip)")
    args = ap.parse_args()
    for spec in args.clip:
        name, path = spec.split("=", 1)
        load(name, path, args.width)
    set_mode(args.start or args.clip[0].split("=", 1)[0])
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
