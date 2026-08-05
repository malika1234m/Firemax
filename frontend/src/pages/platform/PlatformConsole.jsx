import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShieldAlert, Building2, Camera, Activity, Bell, Database, Radio, Cpu,
  LogOut, RefreshCw, CheckCircle2, AlertTriangle, DollarSign, CreditCard,
  LayoutGrid, Users, Package, MessageSquare, Save, Server,
} from 'lucide-react'
import { apiFetch, apiJson } from '../../lib/api'

function fmtUptime(s) {
  if (s == null) return '—'
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60)
  if (d) return `${d}d ${h}h`
  if (h) return `${h}h ${m}m`
  return `${m}m`
}

const TABS = [
  { id: 'overview',   label: 'Overview',   icon: LayoutGrid },
  { id: 'tenants',    label: 'Tenants',    icon: Building2 },
  { id: 'billing',    label: 'Billing',    icon: DollarSign },
  { id: 'plans',      label: 'Plans',      icon: Package },
  { id: 'pipelines',  label: 'Pipelines',  icon: Activity },
  { id: 'complaints', label: 'Complaints', icon: MessageSquare },
]

export default function PlatformConsole() {
  const navigate = useNavigate()
  const [me,   setMe]   = useState(null)
  const [ready, setReady] = useState(false)
  const [tab,  setTab]  = useState('overview')
  const [overview, setOverview] = useState(null)

  const loadOverview = useCallback(() => {
    apiFetch('/platform/overview').then(r => r.ok ? r.json() : null).then(o => o && setOverview(o)).catch(() => {})
  }, [])

  useEffect(() => {
    apiFetch('/platform/auth/me').then(r => {
      if (!r.ok) { navigate('/platform/login', { replace: true }); return null }
      return r.json()
    }).then(u => { if (u) { setMe(u); setReady(true); loadOverview() } })
      .catch(() => navigate('/platform/login', { replace: true }))
  }, [navigate, loadOverview])

  useEffect(() => {
    if (!ready) return
    const id = setInterval(loadOverview, 15000)
    return () => clearInterval(id)
  }, [ready, loadOverview])

  const logout = async () => {
    await apiJson('/platform/auth/logout', { method: 'POST' }).catch(() => {})
    navigate('/platform/login', { replace: true })
  }

  if (!ready) {
    return <div className="min-h-screen bg-void flex items-center justify-center">
      <span className="w-6 h-6 rounded-full border-2 border-slate-700 border-t-slate-300 animate-spin" />
    </div>
  }

  const operational = overview?.status === 'operational'

  return (
    <div className="min-h-screen bg-void text-white">
      <header className="sticky top-0 z-20 backdrop-blur-md bg-void/80 border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 sm:px-10 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <ShieldAlert size={18} className="text-slate-400" />
            <span className="font-raj font-bold text-[16px]">FiremeX Platform</span>
            <span className="text-[9px] font-bold tracking-[0.15em] uppercase text-slate-500 bg-white/[0.05] border border-white/[0.08] rounded px-1.5 py-0.5">Internal</span>
          </div>
          <div className="flex items-center gap-3">
            {overview && (
              <span className={`hidden sm:flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-md border
                ${operational ? 'text-safe bg-safe/10 border-safe/25' : 'text-hazard bg-hazard/10 border-hazard/25'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${operational ? 'bg-safe live-dot' : 'bg-hazard'}`} />
                {operational ? 'Operational' : 'Degraded'}
              </span>
            )}
            <span className="text-[12px] text-slate-500">{me?.email}</span>
            <button onClick={logout} className="text-slate-600 hover:text-hazard transition-colors" title="Log out"><LogOut size={15} /></button>
          </div>
        </div>
        {/* tab nav */}
        <div className="max-w-7xl mx-auto px-6 sm:px-10 flex gap-1 overflow-x-auto">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
                    className={`flex items-center gap-1.5 text-[13px] font-medium px-3 py-2.5 border-b-2 transition-colors whitespace-nowrap
                      ${tab === id ? 'border-slate-200 text-white' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 sm:px-10 py-8">
        {tab === 'overview'   && <OverviewSection overview={overview} onRefresh={loadOverview} />}
        {tab === 'tenants'    && <TenantsSection />}
        {tab === 'billing'    && <BillingSection />}
        {tab === 'plans'      && <PlansSection />}
        {tab === 'pipelines'  && <PipelinesSection />}
        {tab === 'complaints' && <ComplaintsSection />}
      </main>
    </div>
  )
}

/* ── Overview ─────────────────────────────────────────── */
function OverviewSection({ overview, onRefresh }) {
  if (!overview) return <Loading />
  const operational = overview.status === 'operational'
  const infra = overview.infra
  return (
    <div className="space-y-8">
      <div className={`rounded-xl border px-5 py-4 flex items-center gap-3 ${operational ? 'bg-safe/[0.06] border-safe/25' : 'bg-hazard/[0.06] border-hazard/25'}`}>
        {operational ? <CheckCircle2 size={20} className="text-safe" /> : <AlertTriangle size={20} className="text-hazard" />}
        <div className="flex-1">
          <p className={`font-raj font-bold text-[16px] ${operational ? 'text-safe' : 'text-hazard'}`}>{operational ? 'All systems operational' : 'System degraded'}</p>
          <p className="text-[12px] text-slate-500">Uptime {fmtUptime(overview.uptime_seconds)}</p>
        </div>
        <button onClick={onRefresh} className="flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-slate-300"><RefreshCw size={13} /> Refresh</button>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Building2} label="Companies" value={overview.fleet.companies} />
        <StatCard icon={Server} label="Sites Online" value={`${overview.sites?.online ?? 0}/${overview.sites?.total ?? 0}`} />
        <StatCard icon={Activity} label="Active Pipelines" value={overview.fleet.active_pipelines} sub={`${overview.fleet.cameras} cameras`} />
        <StatCard icon={Bell} label="Alerts (24h)" value={overview.alerts.last_24h} sub={`${overview.alerts.unconfirmed} unconfirmed`} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <InfraCard icon={Database} label="Database" ok={infra.database_connected} detail={infra.database_connected ? `ping ${infra.database_ping_ms}ms` : 'disconnected'} />
        <InfraCard icon={Radio} label="Redis" ok={infra.redis_configured} neutral={!infra.redis_configured} detail={infra.redis_configured ? 'configured' : 'in-memory fallback'} />
        <InfraCard icon={Cpu} label="Detection" neutral detail={`runs at edge · ${overview.detector.process_fps_target} FPS target`} />
        <InfraCard icon={Activity} label="Live Viewers" neutral detail={`${infra.websocket_viewers} connected`} />
      </div>
    </div>
  )
}

/* ── Tenants ──────────────────────────────────────────── */
function TenantsSection() {
  const [data, setData] = useState(null)
  useEffect(() => { apiFetch('/platform/tenants').then(r => r.json()).then(setData).catch(() => {}) }, [])
  if (!data) return <Loading />
  return (
    <Table head={['Company', 'Plan', 'Users', 'Cameras', 'Alerts 24h', 'Status']}>
      {data.tenants.map(t => (
        <tr key={t.org_id} className="border-b border-white/[0.04] last:border-0 text-[13px]">
          <td className="px-4 py-3 text-slate-200 font-medium">{t.name}</td>
          <td className="px-4 py-3 text-slate-400 capitalize">{t.plan} <span className="text-slate-600">· {t.subscription_status}</span></td>
          <td className="px-4 py-3 text-slate-400">{t.users}</td>
          <td className="px-4 py-3"><span className={t.cameras_online < t.cameras_expected ? 'text-hazard' : 'text-slate-300'}>{t.cameras_online}/{t.cameras_expected}</span> <span className="text-slate-600">online</span></td>
          <td className="px-4 py-3 text-slate-400">{t.alerts_24h}</td>
          <td className="px-4 py-3">{t.degraded ? <Badge tone="hazard" icon={AlertTriangle}>Degraded</Badge> : <Badge tone="safe" icon={CheckCircle2}>Healthy</Badge>}</td>
        </tr>
      ))}
    </Table>
  )
}

/* ── Billing ──────────────────────────────────────────── */
function BillingSection() {
  const [data, setData] = useState(null)
  useEffect(() => { apiFetch('/platform/billing').then(r => r.json()).then(setData).catch(() => {}) }, [])
  if (!data) return <Loading />
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={DollarSign} label="MRR" value={`$${data.mrr_usd.toLocaleString()}`} />
        <StatCard icon={DollarSign} label="ARR (est.)" value={`$${data.arr_usd.toLocaleString()}`} />
        <StatCard icon={CreditCard} label="Paying Customers" value={data.paying_customers} />
        <StatCard icon={Building2} label="On Trial" value={data.status_counts.trialing} sub={`${data.status_counts.past_due} past due`} />
      </div>
      <Table head={['Company', 'Plan', 'Status', 'Price', 'Payment method', 'Renews / Trial ends']}>
        {data.customers.map(c => (
          <tr key={c.org_id} className="border-b border-white/[0.04] last:border-0 text-[13px]">
            <td className="px-4 py-3 text-slate-200 font-medium">{c.name}</td>
            <td className="px-4 py-3 text-slate-400 capitalize">{c.plan}</td>
            <td className="px-4 py-3">
              {c.subscription_status === 'active' ? <Badge tone="safe" icon={CheckCircle2}>Active</Badge>
                : c.subscription_status === 'past_due' ? <Badge tone="hazard" icon={AlertTriangle}>Past due</Badge>
                : <Badge tone="neutral">{c.subscription_status}</Badge>}
            </td>
            <td className="px-4 py-3 text-slate-300">{c.price_usd ? `$${c.price_usd}/mo` : '—'}</td>
            <td className="px-4 py-3 text-slate-400">{c.has_payment_method ? 'On file' : '—'}</td>
            <td className="px-4 py-3 text-slate-500">{(c.current_period_end || c.trial_ends_at || '').slice(0, 10) || '—'}</td>
          </tr>
        ))}
      </Table>
    </div>
  )
}

/* ── Plans (editable) ─────────────────────────────────── */
function PlansSection() {
  const [plans, setPlans] = useState(null)
  const load = () => apiFetch('/platform/plans').then(r => r.json()).then(d => setPlans(d.plans)).catch(() => {})
  useEffect(() => { load() }, [])
  if (!plans) return <Loading />
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      {plans.map(p => <PlanCard key={p.plan_id} plan={p} onSaved={load} />)}
    </div>
  )
}

function PlanCard({ plan, onSaved }) {
  const [label, setLabel] = useState(plan.label)
  const [price, setPrice] = useState(plan.price_usd)
  const [cams, setCams]   = useState(plan.max_cameras)
  const [seats, setSeats] = useState(plan.max_users)
  const [features, setFeatures] = useState((plan.features || []).join('\n'))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const save = async () => {
    setSaving(true); setSaved(false)
    try {
      await apiJson(`/platform/plans/${plan.plan_id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          label, price_usd: Number(price), max_cameras: Number(cams), max_users: Number(seats),
          features: features.split('\n').map(f => f.trim()).filter(Boolean),
        }),
      })
      setSaved(true); onSaved()
      setTimeout(() => setSaved(false), 2000)
    } finally { setSaving(false) }
  }

  return (
    <div className="glass-card border border-white/[0.07] rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-wider text-slate-600">{plan.plan_id}</span>
        {plan.plan_id === 'trial' && <span className="text-[10px] text-slate-600">free</span>}
      </div>
      <Field label="Label"><input className="field" value={label} onChange={e => setLabel(e.target.value)} /></Field>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Price $/mo"><input type="number" className="field" value={price} onChange={e => setPrice(e.target.value)} disabled={plan.plan_id === 'trial'} /></Field>
        <Field label="Cameras"><input type="number" className="field" value={cams} onChange={e => setCams(e.target.value)} /></Field>
        <Field label="Users"><input type="number" className="field" value={seats} onChange={e => setSeats(e.target.value)} /></Field>
      </div>
      <Field label="Features (one per line)">
        <textarea rows={4} className="field resize-none text-[12px]" value={features} onChange={e => setFeatures(e.target.value)} />
      </Field>
      <button onClick={save} disabled={saving}
              className="w-full flex items-center justify-center gap-1.5 bg-slate-200 text-void text-[13px] font-semibold py-2 rounded-lg hover:bg-white disabled:opacity-40 transition-colors">
        {saved ? <><CheckCircle2 size={14} /> Saved</> : <><Save size={14} /> {saving ? 'Saving…' : 'Save Plan'}</>}
      </button>
    </div>
  )
}

/* ── Pipelines & models ───────────────────────────────── */
function PipelinesSection() {
  const [data, setData] = useState(null)
  const load = () => apiFetch('/platform/pipelines').then(r => r.json()).then(setData).catch(() => {})
  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id) }, [])
  if (!data) return <Loading />
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <InfraCard icon={Cpu} label="Detection Model" neutral detail={`${data.model.model_path} · runs at edge`} />
        <InfraCard icon={Activity} label="Pipelines Online" neutral detail={`${data.online} / ${data.total}`} />
        <InfraCard icon={Radio} label="Default Threshold" neutral detail={`${Math.round(data.model.default_confidence_threshold * 100)}% · ${data.model.process_fps_target} FPS`} />
      </div>
      <Table head={['Camera', 'Company', 'Zone', 'FPS', 'Inference', 'Last frame', 'Status']}>
        {data.pipelines.map(p => (
          <tr key={p.camera_id} className="border-b border-white/[0.04] last:border-0 text-[13px]">
            <td className="px-4 py-3 text-slate-200 font-medium">{p.camera_name}</td>
            <td className="px-4 py-3 text-slate-400">{p.org_name}</td>
            <td className="px-4 py-3 text-slate-500">{p.zone || '—'}</td>
            <td className="px-4 py-3 text-slate-300 font-mono">{p.fps}</td>
            <td className="px-4 py-3 text-slate-300 font-mono">{p.inference_ms}ms</td>
            <td className="px-4 py-3 text-slate-500 font-mono">{p.last_frame_age_s == null ? '—' : `${p.last_frame_age_s}s ago`}</td>
            <td className="px-4 py-3">{p.online ? <Badge tone="safe" icon={CheckCircle2}>Online</Badge> : <Badge tone="hazard" icon={AlertTriangle}>Offline</Badge>}</td>
          </tr>
        ))}
      </Table>
      {data.pipelines.length === 0 && <p className="text-slate-600 text-sm text-center py-6">No active pipelines.</p>}
    </div>
  )
}

/* ── Complaints ───────────────────────────────────────── */
function ComplaintsSection() {
  const [data, setData] = useState(null)
  const load = () => apiFetch('/platform/complaints').then(r => r.json()).then(setData).catch(() => {})
  useEffect(() => { load() }, [])
  if (!data) return <Loading />

  const setStatus = async (id, status) => {
    await apiJson(`/platform/complaints/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) })
    load()
  }

  if (data.complaints.length === 0) return <p className="text-slate-600 text-sm text-center py-10">No complaints filed. 🎉</p>

  return (
    <div className="space-y-3">
      <p className="text-[12px] text-slate-500">{data.open_count} open of {data.complaints.length} total</p>
      {data.complaints.map(c => (
        <div key={c.complaint_id} className="glass-card border border-white/[0.07] rounded-xl p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[13px] text-slate-200 font-medium">{c.subject}</span>
                <span className="text-[10px] uppercase tracking-wider text-slate-500 bg-white/[0.04] border border-white/[0.07] rounded px-1.5 py-0.5">{c.category}</span>
              </div>
              <p className="text-[12px] text-slate-400 mt-1.5">{c.message}</p>
              <p className="text-[11px] text-slate-600 mt-2">{c.org_name} · {c.user_name} ({c.user_email}) · {(c.created_at || '').slice(0, 10)}</p>
            </div>
            <div className="shrink-0">
              {c.status === 'resolved' ? <Badge tone="safe" icon={CheckCircle2}>Resolved</Badge>
                : c.status === 'in_progress' ? <Badge tone="neutral">In progress</Badge>
                : <Badge tone="hazard" icon={AlertTriangle}>Open</Badge>}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/[0.05]">
            {['open', 'in_progress', 'resolved'].map(s => (
              <button key={s} onClick={() => setStatus(c.complaint_id, s)}
                      className={`text-[11px] font-medium px-2.5 py-1 rounded-md border transition-colors capitalize
                        ${c.status === s ? 'bg-white/[0.08] text-white border-white/20' : 'text-slate-500 border-white/[0.08] hover:text-slate-300'}`}>
                {s.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── shared bits ──────────────────────────────────────── */
function Loading() {
  return <div className="flex justify-center py-16"><span className="w-6 h-6 rounded-full border-2 border-slate-700 border-t-slate-300 animate-spin" /></div>
}
function StatCard({ icon: Icon, label, value, sub }) {
  return (
    <div className="glass-card border border-white/[0.07] rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        <Icon size={14} className="text-slate-500" />
      </div>
      <p className="font-raj font-bold text-[24px] text-white leading-none">{value}</p>
      {sub && <p className="text-[11px] text-slate-600 mt-1.5">{sub}</p>}
    </div>
  )
}
function InfraCard({ icon: Icon, label, ok, neutral, detail }) {
  const color = neutral ? 'text-slate-500' : ok ? 'text-safe' : 'text-hazard'
  return (
    <div className="glass-card border border-white/[0.07] rounded-xl p-4 flex items-center gap-3">
      <Icon size={18} className={color} />
      <div className="min-w-0">
        <p className="text-[12px] text-slate-300 font-medium">{label}</p>
        <p className={`text-[11px] truncate ${color}`}>{detail}</p>
      </div>
    </div>
  )
}
function Table({ head, children }) {
  return (
    <div className="glass-card border border-white/[0.07] rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-slate-600 border-b border-white/[0.06]">
              {head.map(h => <th key={h} className="px-4 py-3 font-medium whitespace-nowrap">{h}</th>)}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      </div>
    </div>
  )
}
function Badge({ tone, icon: Icon, children }) {
  const cls = tone === 'safe' ? 'text-safe bg-safe/10 border-safe/25'
    : tone === 'hazard' ? 'text-hazard bg-hazard/10 border-hazard/25'
    : 'text-slate-400 bg-white/[0.04] border-white/[0.08]'
  return <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium rounded-md px-2 py-1 border capitalize ${cls}`}>{Icon && <Icon size={11} />}{children}</span>
}
function Field({ label, children }) {
  return <label className="space-y-1 block"><span className="text-[10px] text-slate-500 font-medium">{label}</span>{children}</label>
}
