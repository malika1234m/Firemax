import { useEffect, useState } from 'react'
import { Gauge, Info, Timer } from 'lucide-react'
import { apiFetch, apiJson } from '../../lib/api'
import { useToast } from '../../context/ToastContext'

export default function DetectionSettings() {
  const { toast } = useToast()
  const [org,       setOrg]       = useState(null)
  const [threshold, setThreshold] = useState(50)
  const [cooldown,  setCooldown]  = useState(30)
  const [saving,    setSaving]    = useState(false)

  const load = () => apiFetch('/organizations/me').then(r => r.ok ? r.json() : null).then(o => {
    if (!o) return
    setOrg(o)
    setThreshold(Math.round(o.confidence_threshold * 100))
    setCooldown(o.alert_cooldown_seconds)
  }).catch(() => {})
  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await apiJson('/organizations/me', {
        method: 'PATCH',
        body: JSON.stringify({ confidence_threshold: threshold / 100, alert_cooldown_seconds: Number(cooldown) }),
      })
      toast({ type: 'success', message: 'Detection settings updated — applied to all cameras immediately.' })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Failed to save' })
    } finally {
      setSaving(false)
    }
  }

  if (!org) return null

  return (
    <div className="max-w-xl glass-card border border-white/[0.07] rounded-xl p-6 space-y-6">
      <div>
        <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">Detection Tuning</h2>
        <p className="text-[11px] text-slate-600 mt-0.5">Applies live to every camera in your organization — no restart needed.</p>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Gauge size={13} className="text-slate-500" />
            <span className="text-[12px] text-slate-400 font-medium">Detection confidence threshold</span>
            <span className="ml-auto font-mono text-[13px] text-brand">{threshold}%</span>
          </div>
          <input type="range" min="10" max="99" value={threshold}
                 onChange={e => setThreshold(Number(e.target.value))}
                 className="w-full accent-brand" />
          <div className="flex justify-between text-[10px] text-slate-700">
            <span>More alerts, more false alarms</span>
            <span>Fewer alerts, may miss faint signals</span>
          </div>
          <p className="text-[11px] text-slate-600 flex items-start gap-1.5 pt-1">
            <Info size={12} className="shrink-0 mt-0.5" />
            Minimum AI confidence a detection needs before it becomes an alert.
          </p>
        </div>

        <div className="space-y-2 pt-2 border-t border-white/[0.05]">
          <div className="flex items-center gap-2">
            <Timer size={13} className="text-slate-500" />
            <span className="text-[12px] text-slate-400 font-medium">Alert cooldown</span>
          </div>
          <div className="flex items-center gap-2">
            <input type="number" min="5" max="600" className="field max-w-[140px]" value={cooldown}
                   onChange={e => setCooldown(e.target.value)} />
            <span className="text-[12px] text-slate-600">seconds</span>
          </div>
          <p className="text-[11px] text-slate-600">
            Minimum time between two alerts on the same camera, so a single ongoing fire doesn't flood the Alerts page.
          </p>
        </div>

        <button type="submit" disabled={saving}
                className="bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
          {saving ? 'Saving…' : 'Save Detection Settings'}
        </button>
      </form>
    </div>
  )
}
