"""Stand-in for Home Assistant Core's REST API — development and demo only.

Lets the fully-local add-on be developed and demonstrated without a Home
Assistant OS box. Add-ons only run under the Supervisor, which HA Container
does not have, so there is otherwise no way to exercise this code on a laptop.

It serves the three endpoints the add-on actually uses — /api/, /api/states and
/api/camera_proxy_stream/<entity> — backing the camera with ml/demo_camera_feed.mp4,
and records everything FiremeX publishes back so ha_agent/replay.py can show it.

    RECEIPTS=/tmp/receipts.jsonl python ha_agent/fake_ha.py

NOT part of the add-on image: this is a test double, and nothing in ha_agent/
imports it.
"""
import json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(ROOT, "ml", "demo_camera_feed.mp4")
RECEIPTS = os.environ.get("RECEIPTS", "/tmp/firemex_ha_receipts.jsonl")
BOUNDARY = "hafakeboundary"

STATES = [
    {"entity_id": "camera.warehouse_bay", "state": "idle",
     "attributes": {"friendly_name": "Warehouse Bay"}},
    {"entity_id": "camera.loading_dock", "state": "idle",
     "attributes": {"friendly_name": "Loading Dock"}},
    {"entity_id": "camera.broken_cam", "state": "unavailable", "attributes": {}},
    {"entity_id": "light.kitchen", "state": "on", "attributes": {}},
    {"entity_id": "siren.warehouse_alarm", "state": "off", "attributes": {}},
]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path == "/api/":          return self._json({"message": "API running."})
        if self.path == "/api/states":    return self._json(STATES)
        if self.path.startswith("/api/camera_proxy_stream/"): return self._mjpeg()
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        with open(RECEIPTS, "a") as fh:
            fh.write(json.dumps({"t": time.time(), "path": self.path, "body": body}) + "\n")
        self._json({"ok": True})

    def _mjpeg(self):
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
        self.end_headers()
        cap = cv2.VideoCapture(VIDEO)
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0); continue
                ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ok: continue
                d = jpg.tobytes()
                self.wfile.write(f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                                 f"Content-Length: {len(d)}\r\n\r\n".encode())
                self.wfile.write(d); self.wfile.write(b"\r\n")
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            cap.release()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8899), H).serve_forever()
