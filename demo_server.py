"""
Firemex Demo Server — port 8001
Upload any image → YOLO detects fire/smoke → shows annotated result
                 → alert appears on dashboard (localhost:5173)
                 → Home Assistant notified
"""

import sys, os, json, base64, uuid, urllib.request, urllib.error
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import cv2, numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault("MODEL_PATH",          "backend/models/fire_model.pt")
os.environ.setdefault("CONFIDENCE_THRESHOLD","0.25")
os.environ.setdefault("MONGODB_URL",         "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME",             "firemax")
os.environ.setdefault("PROCESS_FPS",         "5")

from app.detection.detector import HazardDetector

detector = HazardDetector()
print("[demo] Model loaded — ready\n")

MOCK_API  = "http://localhost:8000"
HA_URL    = "http://localhost:8123"

HTML_FORM = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Firemax — Demo Detection</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#06080D;color:#F1F5F9;font-family:'DM Sans',sans-serif;
         min-height:100vh;display:flex;flex-direction:column;align-items:center;
         padding:40px 20px}
    h1{font-size:28px;font-weight:700;letter-spacing:0.08em;margin-bottom:6px}
    h1 span{color:#EF4444}
    p.sub{color:#64748B;font-size:14px;margin-bottom:40px}
    .card{background:rgba(15,20,30,0.85);border:1px solid rgba(255,255,255,0.08);
          border-radius:16px;padding:32px;width:100%;max-width:640px;margin-bottom:24px}
    label{display:block;font-size:12px;color:#94A3B8;margin-bottom:8px;
          text-transform:uppercase;letter-spacing:0.1em}
    .drop{border:2px dashed rgba(239,68,68,0.4);border-radius:12px;
          padding:48px 20px;text-align:center;cursor:pointer;transition:all 0.2s;
          background:rgba(239,68,68,0.03)}
    .drop:hover{border-color:#EF4444;background:rgba(239,68,68,0.07)}
    .drop input{display:none}
    .drop-icon{font-size:40px;margin-bottom:12px}
    .drop-text{color:#64748B;font-size:14px}
    .drop-text strong{color:#F1F5F9;display:block;font-size:16px;margin-bottom:4px}
    #preview{width:100%;border-radius:8px;margin-top:16px;display:none}
    #filename{font-size:12px;color:#22D3EE;margin-top:8px;display:none}
    button{width:100%;padding:14px;background:#EF4444;color:#fff;border:none;
           border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;
           margin-top:20px;letter-spacing:0.05em;transition:background 0.2s}
    button:hover{background:#DC2626}
    button:disabled{background:#374151;cursor:not-allowed}
    .links{display:flex;gap:12px;margin-top:16px;flex-wrap:wrap}
    .link{flex:1;padding:10px;border:1px solid rgba(255,255,255,0.1);
          border-radius:8px;text-align:center;text-decoration:none;
          font-size:13px;color:#94A3B8;transition:all 0.2s}
    .link:hover{border-color:rgba(255,255,255,0.3);color:#F1F5F9}
  </style>
</head>
<body>
  <h1>FIRE<span>MAX</span></h1>
  <p class="sub">Upload any image — YOLO detects fire & smoke instantly</p>

  <div class="card">
    <form method="POST" action="/detect" enctype="multipart/form-data" id="form">
      <label>Select Image</label>
      <div class="drop" onclick="document.getElementById('file').click()">
        <div class="drop-icon">📷</div>
        <div class="drop-text">
          <strong>Click to upload a fire / smoke image</strong>
          JPG, PNG, screenshots — any format
        </div>
        <input type="file" id="file" name="image" accept="image/*"
               onchange="preview(this)"/>
      </div>
      <img id="preview"/>
      <div id="filename"></div>
      <button type="submit" id="btn">Run Fire Detection</button>
    </form>
  </div>

  <div class="links">
    <a class="link" href="http://localhost:5173" target="_blank">🖥  Firemax Dashboard</a>
    <a class="link" href="http://localhost:8123" target="_blank">🏠  Home Assistant</a>
    <a class="link" href="http://localhost:8000/alerts/" target="_blank">📋  Alert API</a>
  </div>

  <script>
    function preview(input){
      const file = input.files[0];
      if(!file) return;
      document.getElementById('filename').style.display='block';
      document.getElementById('filename').textContent = '📁 '+file.name;
      const reader = new FileReader();
      reader.onload = e => {
        const img = document.getElementById('preview');
        img.src = e.target.result;
        img.style.display = 'block';
      };
      reader.readAsDataURL(file);
    }
    document.getElementById('form').onsubmit = () => {
      const btn = document.getElementById('btn');
      btn.disabled = true;
      btn.textContent = 'Detecting...';
    };
  </script>
</body>
</html>"""

RESULT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Detection Result — Firemax</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#06080D;color:#F1F5F9;font-family:'DM Sans',sans-serif;
         min-height:100vh;display:flex;flex-direction:column;align-items:center;
         padding:40px 20px}}
    h1{{font-size:24px;font-weight:700;letter-spacing:0.08em;margin-bottom:4px}}
    h1 span{{color:#EF4444}}
    .status{{font-size:28px;font-weight:800;margin:24px 0 8px;
             color:{status_color}}}
    .sub{{color:#64748B;font-size:13px;margin-bottom:32px}}
    .card{{background:rgba(15,20,30,0.85);border:1px solid {border_color};
           border-radius:16px;padding:24px;width:100%;max-width:800px;
           margin-bottom:20px}}
    img.result{{width:100%;border-radius:10px;margin-bottom:20px}}
    table{{width:100%;border-collapse:collapse}}
    th{{text-align:left;padding:8px 12px;font-size:11px;color:#64748B;
        text-transform:uppercase;letter-spacing:0.1em;
        border-bottom:1px solid rgba(255,255,255,0.07)}}
    td{{padding:10px 12px;font-size:14px;border-bottom:1px solid rgba(255,255,255,0.04)}}
    .badge{{display:inline-block;padding:3px 10px;border-radius:20px;
            font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase}}
    .fire{{background:rgba(239,68,68,0.2);color:#FCA5A5}}
    .smoke{{background:rgba(251,146,60,0.2);color:#FED7AA}}
    .conf{{font-family:monospace;font-size:15px;font-weight:700}}
    .links{{display:flex;gap:12px;margin-top:16px;flex-wrap:wrap;width:100%;max-width:800px}}
    .link{{flex:1;padding:12px;border:1px solid rgba(255,255,255,0.1);
           border-radius:8px;text-align:center;text-decoration:none;
           font-size:13px;color:#94A3B8;transition:all 0.2s}}
    .link:hover{{border-color:rgba(255,255,255,0.3);color:#F1F5F9}}
    .pill{{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;
           border-radius:20px;font-size:12px;font-weight:600;margin:4px}}
    .ok{{background:rgba(16,185,129,0.15);color:#6EE7B7;border:1px solid rgba(16,185,129,0.3)}}
    .warn{{background:rgba(245,158,11,0.15);color:#FCD34D;border:1px solid rgba(245,158,11,0.3)}}
    .systems{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}}
    a.back{{display:inline-block;margin-top:8px;color:#EF4444;
            font-size:14px;text-decoration:none}}
  </style>
</head>
<body>
  <h1>FIRE<span>MAX</span> — Detection Result</h1>
  <div class="status">{status_icon} {status_text}</div>
  <div class="sub">{det_count} detection(s) found in {elapsed_ms}ms</div>

  <div class="card">
    <img class="result" src="data:image/jpeg;base64,{annotated_b64}"/>
    {table_html}
  </div>

  <div class="card">
    <div style="font-size:12px;color:#64748B;text-transform:uppercase;
                letter-spacing:0.1em;margin-bottom:12px">Systems Notified</div>
    <div class="systems">
      {system_pills}
    </div>
  </div>

  <div class="links">
    <a class="link" href="/" >⬅  Run Another Test</a>
    <a class="link" href="http://localhost:5173" target="_blank">🖥  View Dashboard</a>
    <a class="link" href="http://localhost:8123" target="_blank">🏠  Home Assistant</a>
  </div>
</body>
</html>"""


def inject_alert_to_mock(camera_name, hazard_type, confidence, frame_b64):
    """POST annotated alert with frame to mock server → appears on dashboard."""
    payload = json.dumps({
        "camera_id":   "demo-cam",
        "camera_name": camera_name,
        "hazard_type": hazard_type,
        "confidence":  confidence,
        "timestamp":   datetime.utcnow().isoformat(),
        "frame_b64":   frame_b64,        # annotated JPEG with boxes drawn
    }).encode()
    req = urllib.request.Request(
        f"{MOCK_API}/alerts/",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status == 200
    except Exception as e:
        print(f"  [warn] Could not inject alert: {e}")
        return False


def notify_ha(hazard_type, camera_name, confidence):
    """Send webhook to Home Assistant."""
    data = json.dumps({
        "hazard_type": hazard_type,
        "camera_name": camera_name,
        "confidence":  confidence,
        "timestamp":   datetime.utcnow().isoformat(),
    }).encode()
    req = urllib.request.Request(
        f"{HA_URL}/api/webhook/firemax_hazard_alert",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


class DemoHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def do_GET(self):
        if self.path == "/":
            self._respond(200, "text/html", HTML_FORM.encode())
        else:
            self._respond(404, "text/plain", b"Not found")

    def do_POST(self):
        if self.path != "/detect":
            self._respond(404, "text/plain", b"Not found")
            return

        import time
        t0 = time.time()

        # Parse multipart form manually
        content_type = self.headers.get("Content-Type", "")
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[9:].strip().encode()
        if not boundary:
            self._respond(400, "text/plain", b"Bad content type")
            return
        length   = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        # Extract image bytes between boundaries
        parts    = raw_body.split(b"--" + boundary)
        img_bytes = None
        for part in parts:
            if b'name="image"' in part or b"name='image'" in part:
                # Split headers from body
                idx = part.find(b"\r\n\r\n")
                if idx != -1:
                    img_bytes = part[idx+4:].rstrip(b"\r\n")
                    break
        if img_bytes is None or len(img_bytes) == 0:
            self._respond(400, "text/plain", b"No image uploaded")
            return

        # Decode image
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            self._respond(400, "text/plain", b"Cannot decode image")
            return

        # Run detection
        detections = detector.detect(frame)
        hazards    = detector.is_hazard(detections)

        # Draw boxes on frame
        COLORS = {"fire": (0, 0, 255), "smoke": (0, 140, 255)}
        out = frame.copy()
        for d in hazards:
            col  = COLORS.get(d.label, (0, 0, 255))
            x1,y1,x2,y2 = int(d.x1),int(d.y1),int(d.x2),int(d.y2)
            cv2.rectangle(out, (x1,y1), (x2,y2), col, 3)
            label = f"{d.label.upper()} {d.confidence:.0%}"
            (tw,th),_ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
            cv2.rectangle(out, (x1, y1-th-14), (x1+tw+10, y1), col, -1)
            cv2.putText(out, label, (x1+5, y1-7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2)

        # Encode annotated frame
        _, jpeg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 88])
        frame_b64 = base64.b64encode(jpeg.tobytes()).decode()

        elapsed = int((time.time() - t0) * 1000)

        # Build results table
        if hazards:
            rows = "".join(
                f"<tr>"
                f"<td><span class='badge {d.label}'>{d.label}</span></td>"
                f"<td class='conf'>{d.confidence:.1%}</td>"
                f"<td>{int(d.x1)},{int(d.y1)} → {int(d.x2)},{int(d.y2)}</td>"
                f"</tr>"
                for d in hazards
            )
            table_html = f"""
            <table>
              <tr>
                <th>Hazard Type</th><th>Confidence</th><th>Location (pixels)</th>
              </tr>
              {rows}
            </table>"""
            top        = max(hazards, key=lambda d: d.confidence)
            status_txt = f"{top.label.upper()} DETECTED"
            status_col = "#EF4444"
            border_col = "rgba(239,68,68,0.5)"
            status_ico = "🔥" if top.label == "fire" else "💨"

            # Notify all systems
            ha_ok   = notify_ha(top.label, "Demo Camera", top.confidence)
            dash_ok = inject_alert_to_mock("Demo Camera", top.label,
                                           top.confidence, frame_b64)

            pills = [
                f"<span class='pill ok'>✅ YOLO Detection</span>",
                f"<span class='pill {'ok' if dash_ok else 'warn'}'>{'✅' if dash_ok else '⚠️'} Dashboard (with image)</span>",
                f"<span class='pill {'ok' if ha_ok else 'warn'}'>{'✅' if ha_ok else '⚠️'} Home Assistant</span>",
                f"<span class='pill warn'>⚙️ Email (add SMTP to .env)</span>",
            ]

            print(f"\n  🔥 DETECTED: {top.label.upper()} at {top.confidence:.1%}")
            print(f"     → Dashboard injected: {dash_ok}")
            print(f"     → HA notified: {ha_ok}")
        else:
            table_html = "<p style='color:#64748B;text-align:center;padding:20px'>No fire or smoke detected in this image.</p>"
            status_txt = "NO HAZARD DETECTED"
            status_col = "#22D3EE"
            border_col = "rgba(34,211,238,0.3)"
            status_ico = "✅"
            pills      = [f"<span class='pill ok'>✅ System healthy</span>"]
            print("  ✅ No hazard detected")

        html = RESULT_TEMPLATE.format(
            status_icon   = status_ico,
            status_text   = status_txt,
            status_color  = status_col,
            border_color  = border_col,
            det_count     = len(hazards),
            elapsed_ms    = elapsed,
            annotated_b64 = frame_b64,
            table_html    = table_html,
            system_pills  = "".join(pills),
        )
        self._respond(200, "text/html", html.encode())

    def _respond(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = 8001
    server = HTTPServer(("", port), DemoHandler)
    print("="*52)
    print(f"  Firemax Demo Server")
    print(f"  http://localhost:{port}")
    print(f"  Upload any image → see fire detected instantly")
    print("="*52)
    server.serve_forever()
