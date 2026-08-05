import http from 'http'
import { WebSocketServer } from 'ws'
import { URL } from 'url'

// ── Sample cameras ─────────────────────────────────────────────────────────
let cameras = [
  { camera_id: 'cam-a1b2', name: 'Main Entrance',  stream_url: 'rtsp://192.168.1.10/stream', location: 'Building A – Lobby',       enabled: true,  created_at: ago(7200).toISOString() },
  { camera_id: 'cam-c3d4', name: 'Server Room',     stream_url: 'rtsp://192.168.1.11/stream', location: 'IT Floor – Room 203',      enabled: true,  created_at: ago(7100).toISOString() },
  { camera_id: 'cam-e5f6', name: 'Kitchen Area',    stream_url: 'rtsp://192.168.1.12/stream', location: 'Floor 2 – East Wing',      enabled: true,  created_at: ago(7000).toISOString() },
  { camera_id: 'cam-g7h8', name: 'Parking Lot B1',  stream_url: 'rtsp://192.168.1.13/stream', location: 'Basement – Level B1',      enabled: false, created_at: ago(6900).toISOString() },
]

// ── Sample alerts ──────────────────────────────────────────────────────────
let alertSeq = 1
const mkAlert = (cam_id, cam_name, type, conf, minsAgo) => ({
  alert_id:    `alert-${String(alertSeq++).padStart(4,'0')}`,
  camera_id:   cam_id,
  camera_name: cam_name,
  hazard_type: type,
  confidence:  conf,
  timestamp:   ago(minsAgo * 60).toISOString(),
  frame_b64:   null,
})

let alerts = [
  mkAlert('cam-e5f6', 'Kitchen Area',   'fire',  0.94,   2),
  mkAlert('cam-a1b2', 'Main Entrance',  'smoke', 0.87,  15),
  mkAlert('cam-c3d4', 'Server Room',    'fire',  0.91,  42),
  mkAlert('cam-e5f6', 'Kitchen Area',   'smoke', 0.78,  68),
  mkAlert('cam-a1b2', 'Main Entrance',  'fire',  0.96, 120),
  mkAlert('cam-c3d4', 'Server Room',    'flame', 0.83, 180),
  mkAlert('cam-e5f6', 'Kitchen Area',   'fire',  0.88, 240),
  mkAlert('cam-a1b2', 'Main Entrance',  'smoke', 0.72, 300),
]

// ── HTTP request handler ───────────────────────────────────────────────────
const server = http.createServer((req, res) => {
  const u    = new URL(req.url, 'http://localhost:8000')
  const path = u.pathname.replace(/\/$/, '')   // strip trailing slash

  res.setHeader('Content-Type', 'application/json')
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,DELETE,PATCH,OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return }

  // ── GET /health ──────────────────────────────────────────────────────────
  if (req.method === 'GET' && path === '/health') {
    return ok(res, { status: 'ok', active_cameras: cameras.filter(c => c.enabled).map(c => c.camera_id) })
  }

  // ── GET /cameras ─────────────────────────────────────────────────────────
  if (req.method === 'GET' && path === '/cameras') {
    return ok(res, cameras)
  }

  // ── POST /cameras ─────────────────────────────────────────────────────────
  if (req.method === 'POST' && path === '/cameras') {
    return readBody(req, body => {
      const cam = { camera_id: `cam-${uid()}`, enabled: true, created_at: new Date().toISOString(), ...body }
      cameras.push(cam)
      ok(res, cam)
    })
  }

  // ── DELETE /cameras/:id ───────────────────────────────────────────────────
  const delMatch = path.match(/^\/cameras\/(.+)$/)
  if (req.method === 'DELETE' && delMatch) {
    const id = delMatch[1]
    cameras = cameras.filter(c => c.camera_id !== id)
    return ok(res, { status: 'deleted' })
  }

  // ── PATCH /cameras/:id/toggle ─────────────────────────────────────────────
  const toggleMatch = path.match(/^\/cameras\/(.+)\/toggle$/)
  if (req.method === 'PATCH' && toggleMatch) {
    const id = toggleMatch[1]
    const cam = cameras.find(c => c.camera_id === id)
    if (cam) { cam.enabled = !cam.enabled; return ok(res, { camera_id: id, enabled: cam.enabled }) }
    return res.writeHead(404) && res.end('{}')
  }

  // ── GET /alerts/stats ─────────────────────────────────────────────────────
  if (req.method === 'GET' && path === '/alerts/stats') {
    const counts = {}
    alerts.forEach(a => { counts[a.hazard_type] = (counts[a.hazard_type] || 0) + 1 })
    const by_type = Object.entries(counts).map(([_id, count]) => ({ _id, count })).sort((a,b) => b.count - a.count)
    return ok(res, { total: alerts.length, by_type })
  }

  // ── GET /alerts ───────────────────────────────────────────────────────────
  if (req.method === 'GET' && path === '/alerts') {
    const limit      = parseInt(u.searchParams.get('limit') || '50')
    const hazardType = u.searchParams.get('hazard_type')
    const cameraId   = u.searchParams.get('camera_id')
    let result = [...alerts]
    if (hazardType) result = result.filter(a => a.hazard_type === hazardType)
    if (cameraId)   result = result.filter(a => a.camera_id   === cameraId)
    return ok(res, result.slice(0, limit))
  }

  // ── POST /alerts  (inject alert from demo server with frame_b64) ──────────
  if (req.method === 'POST' && path === '/alerts') {
    return readBody(req, body => {
      const alert = { alert_id: `demo-${Date.now()}`, ...body }
      alerts.unshift(alert)          // add to front so it shows first
      if (alerts.length > 60) alerts.pop()
      console.log(`[alert injected] ${alert.hazard_type} on ${alert.camera_name} ${Math.round(alert.confidence*100)}%`)
      ok(res, alert)
    })
  }

  // ── DELETE /alerts/:id ────────────────────────────────────────────────────
  const alertDelMatch = path.match(/^\/alerts\/(.+)$/)
  if (req.method === 'DELETE' && alertDelMatch) {
    alerts = alerts.filter(a => a.alert_id !== alertDelMatch[1])
    return ok(res, { status: 'deleted' })
  }

  res.writeHead(404); res.end('{}')
})

// ── WebSocket server ───────────────────────────────────────────────────────
// All cameras stream clean — no automatic fire simulation
// Fire is only triggered when you upload an image via http://localhost:8001

const wss = new WebSocketServer({ server })

wss.on('connection', (ws, req) => {
  const u        = new URL(req.url, 'http://localhost:8000')
  const cameraId = u.pathname.split('/').pop()
  let tick = 0

  const interval = setInterval(() => {
    if (ws.readyState !== ws.OPEN) { clearInterval(interval); return }
    tick++

    // No automatic fire — all cameras show clean / no detections
    const detections = []

    ws.send(JSON.stringify({
      camera_id:  cameraId,
      frame_b64:  null,           // real backend sends JPEG; mock shows NoSignal grid
      detections,
      fps:        +(4.5 + Math.random()).toFixed(1),
      timestamp:  new Date().toISOString(),
    }))

  }, 200)

  ws.on('close', () => clearInterval(interval))
})

server.listen(8000, () => {
  console.log('┌──────────────────────────────────────────┐')
  console.log('│  Firemax mock API   http://localhost:8000  │')
  console.log('│  4 cameras  •  clean feeds  •  no auto fire│')
  console.log('│  Upload image at :8001 to trigger alert    │')
  console.log('└──────────────────────────────────────────┘')
})

// ── Helpers ────────────────────────────────────────────────────────────────
function ok(res, data) { res.writeHead(200); res.end(JSON.stringify(data)) }
function ago(secs)      { return new Date(Date.now() - secs * 1000) }
function uid()          { return Math.random().toString(36).slice(2, 8) }
function readBody(req, cb) {
  let body = ''
  req.on('data', d => { body += d })
  req.on('end',  () => cb(JSON.parse(body || '{}')))
}
