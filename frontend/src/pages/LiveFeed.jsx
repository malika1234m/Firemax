import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Grid2x2, Grid3x3, Pin, PinOff } from 'lucide-react'
import { useWebSocket } from '../hooks/useWebSocket'
import { apiFetch } from '../lib/api'
import PageHeader from '../components/PageHeader'

const HAZARDS = new Set(['fire', 'smoke', 'flame', 'gas_fire', 'lpg_fire', 'chemical_fire', 'gas_shimmer'])
const PIN_STORAGE_KEY = 'firemex_pinned_cameras'

function loadPinned() {
  try { return new Set(JSON.parse(localStorage.getItem(PIN_STORAGE_KEY)) ?? []) } catch { return new Set() }
}

export default function LiveFeed() {
  const [cameras, setCameras] = useState([])
  const [cols,    setCols]    = useState(3)
  const [hazards, setHazards] = useState({})   // camera_id -> hazard detection or null
  const [pinned,  setPinned]  = useState(loadPinned)

  useEffect(() => {
    const load = () => apiFetch('/cameras/').then(r => r.json()).then(setCameras).catch(() => {})
    load()
    const id = setInterval(load, 15_000)
    return () => clearInterval(id)
  }, [])

  const reportHazard = useCallback((cameraId, hazard) => {
    setHazards(h => (h[cameraId] === hazard ? h : { ...h, [cameraId]: hazard }))
  }, [])

  const togglePin = (cameraId) => {
    setPinned(p => {
      const next = new Set(p)
      next.has(cameraId) ? next.delete(cameraId) : next.add(cameraId)
      localStorage.setItem(PIN_STORAGE_KEY, JSON.stringify([...next]))
      return next
    })
  }

  // Pinned cameras surface first, then anything currently alerting, everything else after.
  const sorted = useMemo(() => {
    return [...cameras].sort((a, b) => {
      const aPinned = pinned.has(a.camera_id), bPinned = pinned.has(b.camera_id)
      if (aPinned !== bPinned) return aPinned ? -1 : 1
      const aHazard = !!hazards[a.camera_id], bHazard = !!hazards[b.camera_id]
      if (aHazard !== bHazard) return aHazard ? -1 : 1
      return 0
    })
  }, [cameras, pinned, hazards])

  const pinnedCameras   = sorted.filter(c => pinned.has(c.camera_id))
  const unpinnedCameras = sorted.filter(c => !pinned.has(c.camera_id))
  const activeAlerts    = Object.values(hazards).filter(Boolean).length

  return (
    <div className="space-y-5 fade-up">
      {/* "streaming" was a camera count, not a stream count — it claimed
          cameras were streaming when no agent was running. */}
      <PageHeader title="Live Feed" subtitle={`${cameras.length} camera${cameras.length !== 1 ? 's' : ''}${activeAlerts ? ` · ${activeAlerts} critical detection${activeAlerts !== 1 ? 's' : ''}` : ''}`}>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-white/[0.04] border border-white/[0.07] rounded-lg p-1">
            <button onClick={() => setCols(2)}
                    className={`p-1.5 rounded-md transition-colors ${cols === 2 ? 'bg-brand/15 text-brand' : 'text-slate-500 hover:text-slate-300'}`}>
              <Grid2x2 size={14} />
            </button>
            <button onClick={() => setCols(3)}
                    className={`p-1.5 rounded-md transition-colors ${cols === 3 ? 'bg-brand/15 text-brand' : 'text-slate-500 hover:text-slate-300'}`}>
              <Grid3x3 size={14} />
            </button>
          </div>
          <Link to="/cameras"
                className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg bg-brand text-void hover:bg-brand/85 transition-colors">
            <Plus size={14} /> Add Camera
          </Link>
        </div>
      </PageHeader>

      {cameras.length === 0 ? (
        <div className="glass-card border border-white/[0.06] rounded-xl p-16 flex flex-col items-center gap-4">
          <p className="text-slate-500 text-sm">No cameras streaming yet</p>
          <Link to="/cameras" className="text-xs bg-brand/10 text-brand border border-brand/20 px-4 py-2 rounded-lg hover:bg-brand/20 transition-colors">
            Add Camera
          </Link>
        </div>
      ) : (
        <>
          {pinnedCameras.length > 0 && (
            <div className="space-y-3">
              <h2 className="font-raj font-semibold text-[11px] tracking-[0.1em] text-slate-500 uppercase">Pinned</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {pinnedCameras.map(cam => (
                  <Tile key={cam.camera_id} camera={cam} pinned onTogglePin={togglePin} onHazardChange={reportHazard} />
                ))}
              </div>
            </div>
          )}

          <div className="space-y-3">
            {pinnedCameras.length > 0 && (
              <h2 className="font-raj font-semibold text-[11px] tracking-[0.1em] text-slate-500 uppercase">All Cameras</h2>
            )}
            <div className={`grid grid-cols-1 sm:grid-cols-2 ${cols === 3 ? 'xl:grid-cols-3' : 'xl:grid-cols-2'} gap-5`}>
              {unpinnedCameras.map(cam => (
                <Tile key={cam.camera_id} camera={cam} pinned={false} onTogglePin={togglePin} onHazardChange={reportHazard} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// How long a frame stays "live". The agent relays at ~5fps while watched, so
// anything older than this means frames have stopped arriving.
const FRAME_STALE_MS = 10_000

// Mirrors HAZARD_COLOURS in edge/pipeline.py so a live box and the box burned
// into an alert snapshot are the same colour for the same hazard. Grouped by
// detection mechanism: red = learned model, blue/green = colour rules,
// yellow = optical flow, purple = geometry.
const BOX_COLOURS = {
  fire:          '#ff3b30',
  flame:         '#ff3b30',
  smoke:         '#ff8c00',
  gas_fire:      '#0a84ff',
  lpg_fire:      '#5a5aff',
  chemical_fire: '#00c800',
  gas_shimmer:   '#ffd700',
  person_down:   '#d24bd2',
}

/** Draws the boxes onto the canvas in the frame's own pixel space, so CSS can
 *  scale and crop the result exactly as it would a plain image. */
function drawDetections(ctx, detections, width) {
  // Scale strokes and text with the source resolution, otherwise boxes look
  // hairline on a 1080p frame and clumsy on a 480p one.
  const scale = Math.max(width / 640, 1)
  ctx.lineWidth = 2 * scale
  ctx.font = `${12 * scale}px ui-monospace, monospace`
  ctx.textBaseline = 'alphabetic'

  for (const d of detections) {
    const colour = BOX_COLOURS[d.label?.toLowerCase()] ?? '#c8c8c8'
    const w = d.x2 - d.x1, h = d.y2 - d.y1
    ctx.strokeStyle = colour
    ctx.strokeRect(d.x1, d.y1, w, h)

    const label = `${String(d.label).replace(/_/g, ' ')} ${Math.round(d.confidence * 100)}%`
    const tw = ctx.measureText(label).width
    const th = 16 * scale
    const top = Math.max(d.y1, th)          // keep the caption inside the frame
    ctx.fillStyle = colour
    ctx.fillRect(d.x1, top - th, tw + 8 * scale, th)
    ctx.fillStyle = '#ffffff'
    ctx.fillText(label, d.x1 + 4 * scale, top - 4 * scale)
  }
}

function Tile({ camera, pinned, onTogglePin, onHazardChange }) {
  const { frame, connected } = useWebSocket(camera.camera_id)

  // Whether frames are ACTUALLY arriving — not whether the browser's socket to
  // the cloud is open, and not whether the camera record is enabled. Both of
  // those were previously reported as "Normal"/"Online" for a camera with no
  // agent running at all, which is the wrong direction to be wrong in.
  const [lastFrameAt, setLastFrameAt] = useState(null)
  const [, tick] = useState(0)
  useEffect(() => { if (frame?.frame_b64) setLastFrameAt(Date.now()) }, [frame])
  useEffect(() => {
    const id = setInterval(() => tick(t => t + 1), 2000)   // re-evaluate staleness
    return () => clearInterval(id)
  }, [])
  const live = lastFrameAt !== null && Date.now() - lastFrameAt < FRAME_STALE_MS

  // Render the JPEG and its boxes into one canvas. Compositing them together
  // means the overlay cannot drift out of alignment when the tile is resized
  // or cropped — a separate absolutely-positioned overlay has to replicate
  // object-cover's maths and gets it subtly wrong.
  const canvasRef = useRef(null)
  useEffect(() => {
    if (!live || !frame?.frame_b64) return
    let cancelled = false
    const img = new Image()
    img.onload = () => {
      const canvas = canvasRef.current
      if (cancelled || !canvas) return
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0)
      drawDetections(ctx, frame.detections ?? [], img.naturalWidth)
    }
    img.src = `data:image/jpeg;base64,${frame.frame_b64}`
    return () => { cancelled = true }
  }, [frame, live])

  // Detections belong to the frame they came with; once that frame is stale
  // they are history, not a current hazard.
  const hazards   = live ? (frame?.detections?.filter(d => HAZARDS.has(d.label.toLowerCase())) ?? []) : []
  const topHazard = hazards[0] ?? null

  useEffect(() => {
    onHazardChange(camera.camera_id, topHazard)
  }, [camera.camera_id, topHazard?.label, topHazard?.confidence, onHazardChange])

  return (
    <div className="space-y-2 fade-up">
      <div className={`relative rounded-xl overflow-hidden border transition-all glass-card
        ${topHazard ? 'border-hazard/60 hazard-border' : 'border-white/[0.07]'}`}>

        <div className="relative aspect-video bg-[#06080D] scanlines overflow-hidden">
          {/* Only render the frame while it is fresh. A frozen last frame is
              indistinguishable from a live camera pointed at a quiet scene —
              the most dangerous thing this page could show. */}
          {live && frame?.frame_b64
            ? <canvas ref={canvasRef} className="w-full h-full object-cover" />
            : <div className="w-full h-full flex flex-col items-center justify-center gap-1.5">
                <span className="font-mono text-[10px] text-slate-700 tracking-[0.2em] uppercase">No Signal</span>
                <span className="text-[10px] text-slate-700">
                  {!connected ? 'Reconnecting…' : lastFrameAt ? 'Feed stopped' : 'No agent streaming this camera'}
                </span>
              </div>
          }

          <span className="absolute top-2 left-2 font-mono text-[10px] text-white/80 bg-black/50 px-1.5 py-0.5 rounded">
            {camera.name}
          </span>

          <div className="absolute top-2 right-2 flex items-center gap-1.5">
            <span className={`text-[10px] font-raj font-semibold px-2 py-0.5 rounded uppercase
              ${topHazard ? 'bg-hazard text-white' : live ? 'bg-safe/20 text-safe' : 'bg-slate-800 text-slate-500'}`}>
              {topHazard ? 'Critical' : live ? 'Live' : !connected ? 'Reconnecting' : 'No signal'}
            </span>
            <button onClick={() => onTogglePin(camera.camera_id)}
                    title={pinned ? 'Unpin' : 'Pin to top'}
                    className={`p-1 rounded-md transition-colors ${pinned ? 'bg-brand text-void' : 'bg-black/50 text-white/70 hover:text-white'}`}>
              {pinned ? <PinOff size={11} /> : <Pin size={11} />}
            </button>
          </div>

          {topHazard && (
            <div className="absolute bottom-0 inset-x-0 flex items-center justify-center gap-2 px-3 py-2 bg-hazard/90 backdrop-blur-sm">
              <span className="font-raj font-bold text-[11px] tracking-[0.1em] uppercase text-white capitalize">
                {topHazard.label.replace('_', ' ')} Detected · {Math.round(topHazard.confidence * 100)}%
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="px-1">
        <p className="text-[13px] text-slate-200 font-medium">{camera.name}</p>
        <p className="text-[11px] text-slate-600">Zone: {camera.zone}</p>
        <div className="flex items-center justify-between mt-1.5">
          <span className="font-mono text-[10px] text-slate-600">{camera.ip_address || '—'}</span>
          {/* This reflects the camera RECORD, not the stream — it used to read
              "Online" for a camera nothing was watching. Named for what it is. */}
          <span className={`flex items-center gap-1 text-[10px] ${camera.enabled ? 'text-slate-500' : 'text-slate-600'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${camera.enabled ? 'bg-slate-500' : 'bg-slate-700'}`} />
            {camera.enabled ? 'Enabled' : 'Disabled'}
          </span>
        </div>
      </div>
    </div>
  )
}
