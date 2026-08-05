import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Lightbulb, Power, Fan, Lock, Unlock, Blinds, Thermometer, RefreshCw, WifiOff, Link2, KeyRound, FileCog, CheckCircle2, ArrowRight } from 'lucide-react'
import { apiFetch } from '../lib/api'
import PageHeader from '../components/PageHeader'

const DOMAIN_ICON = {
  light: Lightbulb, switch: Power, fan: Fan, lock: Lock, cover: Blinds, climate: Thermometer,
}

const SETUP_STEPS = [
  { icon: KeyRound, title: 'Create a long-lived access token', text: 'In Home Assistant: profile → Security → Long-Lived Access Tokens → Create.' },
  { icon: Link2,    title: 'Open Settings → Home Assistant', text: 'In FiremeX, go to Settings → Home Assistant (admin only).' },
  { icon: FileCog,  title: 'Enter your HA URL + token', text: 'e.g. http://localhost:8123, paste the token, and Connect. Stored encrypted.' },
  { icon: CheckCircle2, title: 'Refresh this page', text: 'Your connected devices appear below automatically.' },
]

const PREVIEW_DOMAINS = [
  { icon: Lightbulb,    label: 'Lights',   text: 'Turn on/off remotely' },
  { icon: Power,        label: 'Switches', text: 'Cut power to equipment' },
  { icon: Fan,          label: 'Fans',     text: 'Ventilation control' },
  { icon: Lock,         label: 'Locks',    text: 'Unlock doors for evacuation' },
  { icon: Blinds,       label: 'Covers',   text: 'Open vents & shutters' },
  { icon: Thermometer,  label: 'Climate',  text: 'HVAC shutoff on hazard' },
]

export default function HomeDevices() {
  const [status,   setStatus]   = useState(null)
  const [entities, setEntities] = useState([])
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(true)
  const [busy,     setBusy]     = useState(null)

  const load = async () => {
    setLoading(true)
    const s = await apiFetch('/ha/status').then(r => r.json()).catch(() => ({ connected: false }))
    setStatus(s)
    if (s.connected) {
      const res = await apiFetch('/ha/entities')
      if (res.ok) { setEntities(await res.json()); setError('') }
      else { const body = await res.json().catch(() => ({})); setError(body.detail || 'Failed to load devices') }
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const toggle = async (entityId) => {
    setBusy(entityId)
    const res = await apiFetch(`/ha/entities/${entityId}/toggle`, { method: 'POST' })
    setBusy(null)
    if (res.ok) {
      const { is_on } = await res.json()
      setEntities(es => es.map(e => e.entity_id === entityId ? { ...e, is_on, state: is_on ? 'on' : 'off' } : e))
    }
  }

  const grouped = entities.reduce((acc, e) => {
    (acc[e.domain] ??= []).push(e)
    return acc
  }, {})

  return (
    <div className="space-y-6 fade-up">
      <PageHeader title="Home Devices" subtitle="Control connected Home Assistant devices">
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1.5 rounded-lg border
            ${status?.connected ? 'bg-safe/10 text-safe border-safe/25' : 'bg-hazard/10 text-hazard border-hazard/25'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${status?.connected ? 'bg-safe live-dot' : 'bg-hazard'}`} />
            {status?.connected ? 'Connected' : 'Disconnected'}
          </span>
          <button onClick={load} className="flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-slate-300 transition-colors">
            <RefreshCw size={13} className={loading ? 'animate-spin-slow' : ''} /> Refresh
          </button>
        </div>
      </PageHeader>

      {!loading && !status?.connected && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">
          <div className="lg:col-span-3 glass-card border border-white/[0.07] rounded-xl p-6 space-y-5">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-full bg-hazard/10 border border-hazard/25 flex items-center justify-center shrink-0">
                <WifiOff size={18} className="text-hazard" />
              </div>
              <div>
                <p className="text-slate-200 text-sm font-medium">Home Assistant is not connected</p>
                <p className="text-slate-600 text-xs mt-0.5">{error || 'Follow these steps to connect it.'}</p>
              </div>
            </div>
            <div className="space-y-4">
              {SETUP_STEPS.map((step, i) => (
                <div key={step.title} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0 text-[11px] font-mono text-slate-500 mt-0.5">
                    {i + 1}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13px] text-slate-300 font-medium">{step.title}</p>
                    <p className="text-[11px] text-slate-600">{step.text}</p>
                  </div>
                </div>
              ))}
            </div>
            <Link to="/settings/home-assistant"
                  className="inline-flex items-center gap-2 bg-brand text-void text-[13px] font-medium px-4 py-2 rounded-lg hover:bg-brand/85 transition-colors">
              Open Home Assistant settings <ArrowRight size={14} />
            </Link>
          </div>

          <div className="lg:col-span-2 glass-card border border-white/[0.07] rounded-xl p-6 space-y-4">
            <div>
              <h2 className="font-raj font-semibold text-[12px] tracking-[0.1em] text-slate-500 uppercase">What you'll control</h2>
              <p className="text-[11px] text-slate-600 mt-0.5">Once connected, operators can act on these during an incident.</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {PREVIEW_DOMAINS.map(({ icon: Icon, label, text }) => (
                <div key={label} className="border border-white/[0.06] rounded-lg p-3 space-y-1.5">
                  <Icon size={15} className="text-slate-600" />
                  <p className="text-[12px] text-slate-400 font-medium">{label}</p>
                  <p className="text-[10px] text-slate-700">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {status?.connected && entities.length === 0 && !loading && (
        <p className="text-slate-700 text-sm">No controllable devices found (lights, switches, fans, locks, covers, climate).</p>
      )}

      {Object.entries(grouped).map(([domain, items]) => (
        <div key={domain} className="space-y-3">
          <h2 className="font-raj font-semibold text-[12px] tracking-[0.1em] text-slate-500 uppercase">
            {domain} <span className="text-slate-700 normal-case tracking-normal">({items.length})</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map(e => <DeviceCard key={e.entity_id} entity={e} busy={busy === e.entity_id} onToggle={() => toggle(e.entity_id)} />)}
          </div>
        </div>
      ))}
    </div>
  )
}

function DeviceCard({ entity, busy, onToggle }) {
  const Icon = DOMAIN_ICON[entity.domain] ?? Power
  return (
    <div className={`glass-card rounded-xl p-4 border transition-colors flex items-center gap-3
      ${entity.is_on ? 'border-brand/30 bg-brand/[0.04]' : 'border-white/[0.07]'}`}>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 border
        ${entity.is_on ? 'bg-brand/15 border-brand/25 text-brand' : 'bg-white/[0.03] border-white/[0.07] text-slate-500'}`}>
        <Icon size={17} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] text-slate-200 font-medium truncate">{entity.name}</p>
        <p className="text-[11px] text-slate-600 capitalize">{entity.state}</p>
      </div>
      <button onClick={onToggle} disabled={busy}
              className={`w-10 h-[22px] rounded-full transition-colors relative shrink-0 disabled:opacity-50
                ${entity.is_on ? 'bg-brand' : 'bg-slate-700'}`}>
        <span className={`absolute top-0.5 w-[18px] h-[18px] rounded-full bg-white transition-all ${entity.is_on ? 'left-[18px]' : 'left-0.5'}`} />
      </button>
    </div>
  )
}
