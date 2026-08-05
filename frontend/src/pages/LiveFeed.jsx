import { useEffect, useMemo, useState, useCallback } from 'react'
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
      <PageHeader title="Live Feed" subtitle={`${cameras.length} cameras streaming${activeAlerts ? ` · ${activeAlerts} critical detection${activeAlerts !== 1 ? 's' : ''}` : ''}`}>
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

function Tile({ camera, pinned, onTogglePin, onHazardChange }) {
  const { frame, connected } = useWebSocket(camera.camera_id)
  const hazards   = frame?.detections?.filter(d => HAZARDS.has(d.label.toLowerCase())) ?? []
  const topHazard = hazards[0] ?? null

  useEffect(() => {
    onHazardChange(camera.camera_id, topHazard)
  }, [camera.camera_id, topHazard?.label, topHazard?.confidence, onHazardChange])

  return (
    <div className="space-y-2 fade-up">
      <div className={`relative rounded-xl overflow-hidden border transition-all glass-card
        ${topHazard ? 'border-hazard/60 hazard-border' : 'border-white/[0.07]'}`}>

        <div className="relative aspect-video bg-[#06080D] scanlines overflow-hidden">
          {frame?.frame_b64
            ? <img src={`data:image/jpeg;base64,${frame.frame_b64}`} className="w-full h-full object-cover" alt="" />
            : <div className="w-full h-full flex items-center justify-center">
                <span className="font-mono text-[10px] text-slate-700 tracking-[0.2em] uppercase">No Signal</span>
              </div>
          }

          <span className="absolute top-2 left-2 font-mono text-[10px] text-white/80 bg-black/50 px-1.5 py-0.5 rounded">
            {camera.name}
          </span>

          <div className="absolute top-2 right-2 flex items-center gap-1.5">
            <span className={`text-[10px] font-raj font-semibold px-2 py-0.5 rounded uppercase
              ${topHazard ? 'bg-hazard text-white' : connected ? 'bg-safe/20 text-safe' : 'bg-slate-800 text-slate-500'}`}>
              {topHazard ? 'Critical' : connected ? 'Normal' : 'Offline'}
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
          <span className={`flex items-center gap-1 text-[10px] ${camera.enabled ? 'text-safe' : 'text-slate-600'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${camera.enabled ? 'bg-safe' : 'bg-slate-600'}`} />
            {camera.enabled ? 'Online' : 'Offline'}
          </span>
        </div>
      </div>
    </div>
  )
}
