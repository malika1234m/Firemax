import { useEffect, useMemo, useState } from 'react'
import { Search, ChevronLeft, ChevronRight, ShieldAlert, CheckCircle2 } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { formatHazardLabel } from '../lib/format'
import { useToast } from '../context/ToastContext'
import PageHeader from '../components/PageHeader'
import LocalDeploymentNotice from '../components/LocalDeploymentNotice'

const PAGE_SIZE = 8
const RANGES = [
  { key: '7',  label: 'Last 7 days'  },
  { key: '30', label: 'Last 30 days' },
  { key: 'all', label: 'All time'    },
]
const STATUSES = [
  { key: '',            label: 'All statuses' },
  { key: 'unresolved',  label: 'Unresolved'   },
  { key: 'in_progress', label: 'In Progress'  },
  { key: 'resolved',    label: 'Resolved'     },
]

export default function Incidents() {
  const { toast } = useToast()
  const [alerts,  setAlerts]  = useState([])
  const [cameras, setCameras] = useState([])
  const [search,  setSearch]  = useState('')
  const [camera,  setCamera]  = useState('')
  const [range,   setRange]   = useState('all')
  const [status,  setStatus]  = useState('')
  const [page,    setPage]    = useState(1)
  const [resolving, setResolving] = useState(null)   // alert object mid-resolve
  const [promoting, setPromoting] = useState(null)    // alert_id currently promoting

  const load = () => {
    const p = new URLSearchParams({ limit: 200 })
    if (camera) p.set('camera_id', camera)
    if (status) p.set('status', status)
    apiFetch(`/alerts/?${p}`).then(r => r.json()).then(setAlerts).catch(() => {})
  }

  useEffect(() => { apiFetch('/cameras/').then(r => r.json()).then(setCameras).catch(() => {}) }, [])
  useEffect(() => { load(); setPage(1) }, [camera, status])

  const filtered = useMemo(() => {
    const cutoff = range === 'all' ? null : Date.now() - Number(range) * 86400_000
    return alerts.filter(a => {
      if (cutoff && new Date(a.timestamp).getTime() < cutoff) return false
      if (search && !`${a.camera_name} ${a.zone}`.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [alerts, range, search])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems   = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const updateStatus = async (alert, newStatus) => {
    if (newStatus === 'resolved') { setResolving(alert); return }
    await apiFetch(`/alerts/${alert.alert_id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: newStatus }),
    })
    load()
  }

  const handlePromote = async (alertId) => {
    setPromoting(alertId)
    try {
      await apiJson(`/alerts/${alertId}/promote`, { method: 'POST' })
      toast({ type: 'success', message: 'Promoted to incident — Home Assistant and authority contacts notified.' })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Failed to promote alert' })
    } finally {
      setPromoting(null)
    }
  }

  return (
    <div className="space-y-5 fade-up">
      <PageHeader title="Incidents" subtitle="Detection history & review log" />

      {/* ── Filters ──────────────────────────────── */}
      <div className="glass-card border border-white/[0.07] rounded-xl px-4 py-3 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" />
          <input className="field pl-8 py-1.5" placeholder="Search cameras or zones..."
                 value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} />
        </div>

        <select className="field select-field py-1.5 appearance-none" style={{ width: 'auto' }} value={camera} onChange={e => setCamera(e.target.value)}>
          <option value="">All cameras</option>
          {cameras.map(c => <option key={c.camera_id} value={c.camera_id}>{c.name}</option>)}
        </select>

        <select className="field select-field py-1.5 appearance-none" style={{ width: 'auto' }} value={range} onChange={e => { setRange(e.target.value); setPage(1) }}>
          {RANGES.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
        </select>

        <select className="field select-field py-1.5 appearance-none" style={{ width: 'auto' }} value={status} onChange={e => setStatus(e.target.value)}>
          {STATUSES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
      </div>

      {/* ── Table ────────────────────────────────── */}
      <div className="glass-card border border-white/[0.07] rounded-xl overflow-hidden">
        {pageItems.length === 0 ? (
          <LocalDeploymentNotice what="Incident history">
            <p className="text-center text-slate-700 text-sm py-12">No incidents match these filters</p>
          </LocalDeploymentNotice>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-600">
                <th className="px-4 py-2.5 font-medium">Timestamp</th>
                <th className="px-4 py-2.5 font-medium">Camera</th>
                <th className="px-4 py-2.5 font-medium">Zone</th>
                <th className="px-4 py-2.5 font-medium">AI Conf.</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Incident</th>
                <th className="px-4 py-2.5 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {pageItems.map(a => (
                <tr key={a.alert_id} className="border-t border-white/[0.05] text-[12px]">
                  <td className="px-4 py-3 font-mono text-slate-500">{new Date(a.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-300">{a.camera_name}</td>
                  <td className="px-4 py-3 text-slate-500">{a.zone}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-slate-400 w-9">{Math.round(a.confidence * 100)}%</span>
                      <div className="w-16 h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-brand rounded-full" style={{ width: `${a.confidence * 100}%` }} />
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusLabel alert={a} />
                  </td>
                  <td className="px-4 py-3">
                    {a.promoted_to_incident ? (
                      <span className="flex items-center gap-1 text-[10px] font-semibold text-brand uppercase">
                        <CheckCircle2 size={11} /> {a.incident_code}
                      </span>
                    ) : (
                      <button onClick={() => handlePromote(a.alert_id)} disabled={promoting === a.alert_id}
                              className="flex items-center gap-1 text-[10px] font-semibold text-slate-400 border border-white/[0.1] rounded-md px-2 py-1 hover:text-brand hover:border-brand/40 transition-colors disabled:opacity-40">
                        <ShieldAlert size={11} /> {promoting === a.alert_id ? 'Promoting…' : 'Make Incident'}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <select value={a.status} onChange={e => updateStatus(a, e.target.value)}
                            className="select-field-sm bg-white/[0.04] border border-white/[0.08] text-[11px] text-slate-300 rounded-md px-2 py-1 appearance-none">
                      <option value="unresolved">Unresolved</option>
                      <option value="in_progress">In Progress</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* ── Pagination ─────────────────────────── */}
        {filtered.length > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.06] text-[11px] text-slate-600">
            <span>
              Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length} incidents
            </span>
            <div className="flex items-center gap-1">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                      className="p-1.5 rounded-md border border-white/[0.07] disabled:opacity-30 hover:bg-white/[0.04] transition-colors">
                <ChevronLeft size={12} />
              </button>
              <span className="px-2 font-mono">{page} / {totalPages}</span>
              <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
                      className="p-1.5 rounded-md border border-white/[0.07] disabled:opacity-30 hover:bg-white/[0.04] transition-colors">
                <ChevronRight size={12} />
              </button>
            </div>
          </div>
        )}
      </div>

      {resolving && (
        <ResolveModal
          alert={resolving}
          onClose={() => setResolving(null)}
          onDone={() => { setResolving(null); toast({ type: 'success', message: 'Incident resolved.' }); load() }}
        />
      )}
    </div>
  )
}

function StatusLabel({ alert }) {
  if (alert.status === 'resolved')    return <span className="text-safe font-medium">Resolved</span>
  if (alert.status === 'in_progress') return <span className="text-warn font-medium">In Progress</span>
  const color = alert.hazard_type === 'camera_offline' ? 'text-slate-400' : 'text-hazard'
  return <span className={`${color} font-medium`}>{formatHazardLabel(alert.hazard_type)}</span>
}

function ResolveModal({ alert, onClose, onDone }) {
  const [verdict, setVerdict] = useState('')
  const [remark,  setRemark]  = useState('')
  const [error,   setError]   = useState('')
  const [saving,  setSaving]  = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!verdict) { setError('Select whether this was a true fire or a false alarm.'); return }
    if (!remark.trim()) { setError('A remark is required — this trains the detection model.'); return }
    setSaving(true); setError('')
    try {
      await apiJson(`/alerts/${alert.alert_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'resolved', resolution_verdict: verdict, resolution_remark: remark.trim() }),
      })
      onDone()
    } catch (err) {
      setError(err.message || 'Failed to resolve incident')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
      <form onSubmit={submit} className="glass-card border border-white/[0.1] rounded-xl p-5 w-full max-w-md space-y-4">
        <div>
          <p className="font-raj font-semibold text-[14px] text-white">Resolve Incident</p>
          <p className="text-[11px] text-slate-600 mt-0.5">
            {alert.camera_name} · {alert.incident_code ?? alert.alert_id.slice(0, 8)}
          </p>
        </div>

        {error && <p className="text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">{error}</p>}

        <div className="space-y-1.5">
          <span className="text-[11px] text-slate-500 font-medium">Was this a real fire?</span>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" onClick={() => setVerdict('true_fire')}
                    className={`text-[12px] font-medium py-2 rounded-lg border transition-colors
                      ${verdict === 'true_fire' ? 'bg-hazard/15 text-hazard border-hazard/40' : 'text-slate-400 border-white/[0.08] hover:border-white/[0.16]'}`}>
              True Fire
            </button>
            <button type="button" onClick={() => setVerdict('false_alarm')}
                    className={`text-[12px] font-medium py-2 rounded-lg border transition-colors
                      ${verdict === 'false_alarm' ? 'bg-safe/15 text-safe border-safe/40' : 'text-slate-400 border-white/[0.08] hover:border-white/[0.16]'}`}>
              False Alarm
            </button>
          </div>
        </div>

        <label className="space-y-1.5 block">
          <span className="text-[11px] text-slate-500 font-medium">Remark</span>
          <textarea className="field" rows={3} placeholder="What actually happened? This feeds back into model training."
                    value={remark} onChange={e => setRemark(e.target.value)} />
        </label>

        <div className="flex items-center gap-3 pt-1">
          <button type="button" onClick={onClose} className="text-sm text-slate-400 hover:text-slate-200 px-4 py-2 transition-colors">
            Cancel
          </button>
          <button type="submit" disabled={saving}
                  className="ml-auto bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            {saving ? 'Saving…' : 'Mark Resolved'}
          </button>
        </div>
      </form>
    </div>
  )
}
