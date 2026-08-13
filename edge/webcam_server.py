"""Serve a local webcam (or video file) as an MJPEG stream over HTTP.

Why this exists
---------------
The agent normally runs in Docker, and Docker Desktop on macOS and Windows
cannot pass a host camera into a container — DETECTOR_MODE and WEBCAM_DEVICE
are useless there. So instead of getting the camera into the container, this
puts the camera on the network, where the agent can open it like any other
camera.

    laptop webcam --> this script (http://<host>:8080/) --> agent --> FiremeX

Requires only OpenCV, not the ML stack:

    pip install opencv-python

Usage
-----
    python webcam_server.py                 # built-in camera, port 8080
    python webcam_server.py --device 1      # a specific camera
    python webcam_server.py --source clip.mp4   # loop a video file instead
    python webcam_server.py --list          # show what OpenCV can open

Then register a camera in FiremeX whose stream_url is the URL it prints. From
an agent running in Docker on the SAME machine, use:

    http://host.docker.internal:8080/

`localhost` would refer to the container itself, not the laptop.
"""
import argparse
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

BOUNDARY = "firemexframe"


class Source:
    """Latest-frame-wins reader, mirroring the agent's own StreamReader: a slow
    HTTP client must never make the camera fall behind real time."""

    def __init__(self, spec, loop: bool):
        self.spec, self.loop = spec, loop
        self._frame = None
        self._lock = threading.Lock()
        self._running = True
        threading.Thread(target=self._read, daemon=True).start()

    def _open(self):
        cap = cv2.VideoCapture(self.spec)
        if not cap.isOpened():
            raise SystemExit(
                f"Could not open source {self.spec!r}.\n"
                "If this is a camera index, macOS may be withholding camera "
                "permission from your terminal — check System Settings → "
                "Privacy & Security → Camera. Run with --list to see options."
            )
        return cap

    def _read(self):
        cap = self._open()
        while self._running:
            ok, frame = cap.read()
            if not ok:
                if self.loop:                      # video file reached the end
                    cap.release()
                    cap = self._open()
                    continue
                time.sleep(0.5)
                continue
            with self._lock:
                self._frame = frame
        cap.release()

    def latest(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()


class Handler(BaseHTTPRequestHandler):
    source: Source = None
    fps: float = 10.0

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        interval = 1.0 / self.fps
        try:
            while True:
                frame = self.source.latest()
                if frame is None:
                    time.sleep(0.1)
                    continue
                ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ok:
                    self.wfile.write(f"--{BOUNDARY}\r\n".encode())
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                    self.wfile.write(jpeg.tobytes())
                    self.wfile.write(b"\r\n")
                time.sleep(interval)
        except (BrokenPipeError, ConnectionResetError):
            pass          # viewer went away; normal

    def log_message(self, *_args):
        pass              # one line per frame is not useful


def list_devices(maximum: int = 4):
    print("Probing camera indices (a permission prompt may appear)…")
    for idx in range(maximum):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ok, frame = cap.read()
            size = f"{frame.shape[1]}x{frame.shape[0]}" if ok else "opened, no frame"
            print(f"  --device {idx}  →  {size}")
        cap.release()
    print("\nOn a Mac, index 0 is often an iPhone via Continuity Camera rather\n"
          "than the built-in webcam. Pick by resolution if unsure.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=0, help="camera index (default 0)")
    ap.add_argument("--source", help="video file to loop instead of a camera")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--list", action="store_true", help="list openable cameras and exit")
    args = ap.parse_args()

    if args.list:
        list_devices()
        return

    spec = args.source if args.source else args.device
    Handler.source = Source(spec, loop=bool(args.source))
    Handler.fps = args.fps

    try:
        server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    except OSError as exc:
        raise SystemExit(
            f"Could not listen on port {args.port}: {exc}\n"
            f"Something else is probably using it — check with "
            f"`lsof -iTCP:{args.port} -sTCP:LISTEN`, or pick another with "
            f"--port 8090."
        )
    print(f"serving {spec!r} at:")
    print(f"  http://localhost:{args.port}/               (this machine)")
    print(f"  http://host.docker.internal:{args.port}/    ← use this as the FiremeX stream_url")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping…")


if __name__ == "__main__":
    sys.exit(main())
