import { useEffect, useState } from 'react'
import { Trash2, Power, Video, VideoOff, Wifi, CheckCircle2, XCircle, MapPin, Camera as CameraIcon } from 'lucide-react'
import { apiFetch } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import PageHeader from '../components/PageHeader'
import LocalDeploymentNotice from '../components/LocalDeploymentNotice'

const EMPTY_FORM = {
  name: '', ip_address: '', zone: '', resolution: '1080p (Full HD)', frame_rate: 30, ai_tracking: true,
}
const RESOLUTIONS = ['480p (SD)', '720p (HD)', '1080p (Full HD)', '4K (Ultra HD)']
const FRAME_RATES = [15, 24, 30, 60]

export default function Cameras() {
  const { toast } = useToast()
  const confirm = useConfirm()
  const [cameras, setCameras] = useState([])
  const [health,  setHealth]  = useState(null)
  const [zones,   setZones]   = useState([])
  const [form,    setForm]    = useState(EMPTY_FORM)
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)

  const load = () => {
    apiFetch('/cameras/').then(r => r.json()).then(setCameras).catch(() => {})
    // Liveness comes from agent heartbeats, not from `enabled` — see
    // GET /cameras/health.
    apiFetch('/cameras/health').then(r => r.ok ? r.json() : null).then(setHealth).catch(() => {})
  }
  useEffect(() => {
    load()
    apiFetch('/cameras/zones').then(r => r.json()).then(zs => {
      setZones(zs)
      setForm(f => ({ ...f, zone: f.zone || zs[0] || '' }))
    }).catch(() => {})
  }, [])

  const field = (key) => ({
    value: form[key],
    onChange: e => { setForm(f => ({ ...f, [key]: e.target.value })); setTestResult(null) },
  })

  const handleTest = async () => {
    if (!form.ip_address.trim()) { setError('Enter an IP address or URL to test.'); return }
    setTesting(true); setError('')
    const res = await apiFetch('/cameras/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip_address: form.ip_address }),
    }).then(r => r.json()).catch(() => null)
    setTesting(false)
    setTestResult(res)
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.ip_address.trim()) { setError('Camera name and IP address / URL are required.'); return }
    setLoading(true); setError('')
    const target = form.ip_address.includes('://') ? form.ip_address : `rtsp://${form.ip_address}`
    const res = await apiFetch('/cameras/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.name,
        stream_url: target,
        ip_address: form.ip_address,
        zone: form.zone,
        resolution: form.resolution,
        frame_rate: Number(form.frame_rate),
        ai_tracking: form.ai_tracking,
      }),
    })
    setLoading(false)
    if (!res.ok) { setError('Failed to add camera — check the stream URL.'); return }
    setForm(f => ({ ...EMPTY_FORM, zone: f.zone }))
    setTestResult(null)
    toast({ type: 'success', message: `${form.name} was added.` })
    load()
  }

  const handleDelete = async (id, name) => {
    const ok = await confirm({ title: 'Remove this camera?', message: `${name}'s stream will stop immediately.`, danger: true, confirmLabel: 'Remove' })
    if (!ok) return
    await apiFetch(`/cameras/${id}`, { method: 'DELETE' })
    toast({ type: 'success', message: `${name} was removed.` })
    load()
  }

  const handleToggle = async (id) => {
    await apiFetch(`/cameras/${id}/toggle`, { method: 'PATCH' })
    load()
  }

  const onlineCount = cameras.filter(c => c.enabled).length
  const zoneCount = new Set(cameras.map(c => c.zone)).size

  return (
    <div className="max-w-6xl space-y-6 fade-up">
      <PageHeader title="Camera Management" subtitle="Add or remove cameras from the secure network" />

      {cameras.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Total Cameras" value={cameras.length} icon={CameraIcon} />
          <StatCard label="Online" value={onlineCount} icon={Power} tone="safe" />
          <StatCard label="Zones Covered" value={zoneCount} icon={MapPin} />
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6 items-start">
        {/* ── Add New Device form ────────────────────── */}
        <form onSubmit={handleAdd} className="xl:col-span-2 glass-card border border-white/[0.09] rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <Video size={14} className="text-brand" />
            <div>
              <p className="font-raj font-semibold text-[13px] text-white">Add New Device</p>
              <p className="text-[11px] text-slate-600">Configure a new camera stream for the secure network.</p>
            </div>
          </div>

          {error && <p className="text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">{error}</p>}

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-1 gap-3">
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Camera Name</span>
              <input className="field" placeholder="e.g. Perimeter North-West" {...field('name')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">IP Address / URL</span>
              <input className="field font-mono text-xs" placeholder="192.168.1.105" {...field('ip_address')} />
            </label>

            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Zone Assignment</span>
              <select className="field select-field appearance-none" {...field('zone')}>
                {zones.map(z => <option key={z} value={z}>{z}</option>)}
              </select>
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Resolution</span>
              <select className="field select-field appearance-none" {...field('resolution')}>
                {RESOLUTIONS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Frame Rate</span>
              <select className="field select-field appearance-none" {...field('frame_rate')}>
                {FRAME_RATES.map(f => <option key={f} value={f}>{f} FPS</option>)}
              </select>
            </label>
            <label className="flex items-center justify-between pt-5">
              <span className="text-[11px] text-slate-500 font-medium">Enable AI Tracking</span>
              <button type="button"
                      onClick={() => setForm(f => ({ ...f, ai_tracking: !f.ai_tracking }))}
                      className={`w-10 h-[22px] rounded-full transition-colors relative shrink-0 ${form.ai_tracking ? 'bg-brand' : 'bg-slate-700'}`}>
                <span className={`absolute top-0.5 w-[18px] h-[18px] rounded-full bg-white transition-all ${form.ai_tracking ? 'left-[18px]' : 'left-0.5'}`} />
              </button>
            </label>
          </div>

          {/* Preview / test connection */}
          <div className="border border-white/[0.07] rounded-lg p-4 space-y-3">
            <div className="h-20 flex items-center justify-center rounded-md bg-black/30">
              {testResult === null ? (
                <span className="flex items-center gap-2 text-[11px] text-slate-700 uppercase tracking-wider text-center">
                  <VideoOff size={14} /> No active stream selected
                </span>
              ) : testResult.reachable ? (
                <span className="flex items-center gap-2 text-[11px] text-safe uppercase tracking-wider">
                  <CheckCircle2 size={14} /> Reachable at {testResult.host}:{testResult.port}
                </span>
              ) : (
                <span className="flex items-center gap-2 text-[11px] text-hazard uppercase tracking-wider">
                  <XCircle size={14} /> Could not reach {testResult.host}:{testResult.port}
                </span>
              )}
            </div>
            <button type="button" onClick={handleTest} disabled={testing}
                    className="flex items-center gap-1.5 mx-auto text-[11px] text-brand border border-brand/30 rounded-lg px-3 py-1.5 hover:bg-brand/10 transition-colors disabled:opacity-40">
              <Wifi size={12} /> {testing ? 'Testing…' : 'Test Connection'}
            </button>
          </div>

          <div className="flex items-center gap-3 pt-1 border-t border-white/[0.05]">
            <button type="button" onClick={() => { setForm(f => ({ ...EMPTY_FORM, zone: f.zone })); setTestResult(null); setError('') }}
                    className="text-sm text-slate-400 hover:text-slate-200 px-4 py-2 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={loading}
                    className="ml-auto flex items-center gap-2 bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
              {loading ? 'Adding…' : 'Add Camera →'}
            </button>
          </div>
        </form>

        {/* ── Existing cameras ───────────────────────── */}
        <div className="xl:col-span-3 space-y-3">
          <h2 className="font-raj font-semibold text-[12px] tracking-[0.1em] text-slate-500 uppercase">
            Configured Cameras ({cameras.length})
          </h2>
          {cameras.length === 0 ? (
            <div className="glass-card border border-white/[0.06] rounded-xl">
              <LocalDeploymentNotice what="This list">
                <div className="p-12 flex flex-col items-center gap-3 text-center">
                  <div className="w-12 h-12 rounded-full bg-slate-900 border border-white/[0.06] flex items-center justify-center">
                    <CameraIcon size={20} className="text-slate-700" />
                  </div>
                  <p className="text-slate-500 text-sm">No cameras yet — add your first device on the left.</p>
                </div>
              </LocalDeploymentNotice>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {cameras.map(cam => (
                <div key={cam.camera_id} className="glass-card border border-white/[0.07] rounded-xl p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[13px] text-slate-200 font-medium truncate">{cam.name}</p>
                      <p className="flex items-center gap-1 text-[11px] text-slate-600 mt-0.5">
                        <MapPin size={10} /> {cam.zone}
                      </p>
                    </div>
                    {/* Two independent facts: whether an operator switched the
                        camera on, and whether an agent is actually watching it.
                        Showing "Online" for the former was misleading. */}
                    <span className="flex items-center gap-2 shrink-0">
                      {!cam.enabled && (
                        <span className="text-[10px] text-slate-600">Disabled</span>
                      )}
                      <span className={`flex items-center gap-1 text-[10px] font-medium
                        ${health?.cameras?.[cam.camera_id]?.online ? 'text-safe' : 'text-slate-600'}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${health?.cameras?.[cam.camera_id]?.online ? 'bg-safe' : 'bg-slate-600'}`} />
                        {health?.cameras?.[cam.camera_id]?.online ? 'Live' : 'Not reporting'}
                      </span>
                    </span>
                  </div>
                  <p className="font-mono text-[10px] text-slate-700 truncate">
                    {cam.ip_address || cam.stream_url} · {cam.resolution} · {cam.frame_rate} FPS
                  </p>
                  <div className="flex items-center gap-4 pt-2 border-t border-white/[0.05]">
                    <button onClick={() => handleToggle(cam.camera_id)}
                            className={`flex items-center gap-1.5 text-[11px] transition-colors
                              ${cam.enabled ? 'text-safe hover:text-safe/80' : 'text-slate-600 hover:text-slate-400'}`}>
                      <Power size={11} /> {cam.enabled ? 'Enabled' : 'Disabled'}
                    </button>
                    <button onClick={() => handleDelete(cam.camera_id, cam.name)}
                            className="ml-auto flex items-center gap-1.5 text-[11px] text-slate-700 hover:text-hazard transition-colors">
                      <Trash2 size={11} /> Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, icon: Icon, tone }) {
  const color = tone === 'safe' ? 'text-safe' : 'text-white'
  return (
    <div className="glass-card rounded-xl p-4 border border-white/[0.07]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        <Icon size={14} className="text-slate-500" />
      </div>
      <p className={`font-raj font-bold text-[22px] leading-none ${color}`}>{value}</p>
    </div>
  )
}
