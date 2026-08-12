import { useEffect, useState } from 'react'
import { Server, Plus, Trash2, RefreshCw, Copy, CheckCircle2, KeyRound, X } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import PageHeader from '../components/PageHeader'
import SetupStepper from '../components/SetupStepper'

function timeAgo(iso) {
  if (!iso) return 'never'
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export default function Sites() {
  const { toast } = useToast()
  const confirm = useConfirm()
  const [sites, setSites] = useState([])
  const [name,  setName]  = useState('')
  const [creating, setCreating] = useState(false)
  const [newToken, setNewToken] = useState(null)   // { site, enrollment_token }
  const [copied, setCopied] = useState(false)

  const load = () => apiFetch('/sites/').then(r => r.ok ? r.json() : []).then(setSites).catch(() => {})
  useEffect(() => { load(); const id = setInterval(load, 15000); return () => clearInterval(id) }, [])

  const create = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    try {
      const res = await apiJson('/sites/', { method: 'POST', body: JSON.stringify({ name: name.trim() }) })
      setNewToken(res)
      setName('')
      toast({ type: 'success', message: `Site "${res.site.name}" created.` })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Failed to create site' })
    } finally { setCreating(false) }
  }

  const rotate = async (site) => {
    const ok = await confirm({ title: `Rotate token for ${site.name}?`, message: 'The current agent will stop connecting until you update it with the new token.', danger: true, confirmLabel: 'Rotate' })
    if (!ok) return
    const res = await apiJson(`/sites/${site.site_id}/rotate-token`, { method: 'POST' })
    setNewToken(res)
    toast({ type: 'success', message: 'New token issued.' })
    load()
  }

  const remove = async (site) => {
    const ok = await confirm({ title: `Delete ${site.name}?`, message: 'Its agent will lose access immediately.', danger: true, confirmLabel: 'Delete' })
    if (!ok) return
    await apiFetch(`/sites/${site.site_id}`, { method: 'DELETE' })
    toast({ type: 'success', message: 'Site deleted.' })
    load()
  }

  const copyToken = () => {
    navigator.clipboard?.writeText(newToken.enrollment_token)
    setCopied(true); setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="max-w-5xl space-y-6 fade-up">
      <PageHeader title="Sites" subtitle="Edge agents that run detection on your own network" />

      {/* Removes itself once setup is done — see SetupStepper. */}
      <SetupStepper />

      <p className="text-[12px] text-slate-500 -mt-2 max-w-2xl">
        Each site runs a FiremeX <span className="text-slate-300">edge agent</span> on your local network — it reads your cameras,
        runs detection on your hardware, and reports events here. Camera video never leaves your site.
      </p>

      {/* create */}
      <form onSubmit={create} className="glass-card border border-white/[0.09] rounded-xl p-5 flex flex-col sm:flex-row gap-3 sm:items-end">
        <label className="space-y-1.5 flex-1">
          <span className="text-[11px] text-slate-500 font-medium">New site name</span>
          <input className="field" placeholder="e.g. HQ Warehouse" value={name} onChange={e => setName(e.target.value)} />
        </label>
        <button type="submit" disabled={creating}
                className="flex items-center gap-2 bg-brand text-void text-sm font-medium px-5 py-2.5 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
          <Plus size={15} /> {creating ? 'Creating…' : 'Create Site'}
        </button>
      </form>

      {/* enrollment token reveal (shown once) */}
      {newToken && (
        <div className="glass-card border border-brand/30 rounded-xl p-5 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <KeyRound size={15} className="text-brand" />
              <div>
                <p className="text-[13px] text-slate-200 font-medium">Enrollment token for "{newToken.site.name}"</p>
                <p className="text-[11px] text-slate-600">Shown once. Give it to the edge agent as its <code className="font-mono">AGENT_TOKEN</code>. Store it safely — rotate if lost.</p>
              </div>
            </div>
            <button onClick={() => setNewToken(null)} className="text-slate-600 hover:text-slate-300"><X size={15} /></button>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 min-w-0 truncate font-mono text-[12px] text-brand bg-black/40 border border-white/[0.08] rounded-lg px-3 py-2.5">{newToken.enrollment_token}</code>
            <button onClick={copyToken} className="flex items-center gap-1.5 text-[12px] text-slate-300 border border-white/[0.1] rounded-lg px-3 py-2.5 hover:bg-white/[0.04] transition-colors shrink-0">
              {copied ? <><CheckCircle2 size={13} className="text-safe" /> Copied</> : <><Copy size={13} /> Copy</>}
            </button>
          </div>
        </div>
      )}

      {/* list */}
      {sites.length === 0 ? (
        <div className="glass-card border border-white/[0.06] rounded-xl p-12 flex flex-col items-center gap-3 text-center">
          <div className="w-12 h-12 rounded-full bg-slate-900 border border-white/[0.06] flex items-center justify-center">
            <Server size={20} className="text-slate-700" />
          </div>
          <p className="text-slate-500 text-sm">No sites yet — create one, then run the edge agent with its token.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {sites.map(s => {
            const online = s.status === 'online'
            return (
              <div key={s.site_id} className="glass-card border border-white/[0.07] rounded-xl p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[13px] text-slate-200 font-medium truncate">{s.name}</p>
                    <p className="text-[11px] text-slate-600">{s.agent_version ? `agent v${s.agent_version}` : 'agent not connected'}</p>
                  </div>
                  <span className={`flex items-center gap-1.5 text-[10px] font-medium shrink-0 ${online ? 'text-safe' : 'text-slate-500'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-safe live-dot' : 'bg-slate-600'}`} />
                    {online ? 'Online' : s.status === 'pending' ? 'Awaiting agent' : 'Offline'}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600">Last seen: {timeAgo(s.last_seen_at)}</p>
                <div className="flex items-center gap-4 pt-2 border-t border-white/[0.05]">
                  <button onClick={() => rotate(s)} className="flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-brand transition-colors">
                    <RefreshCw size={11} /> Rotate token
                  </button>
                  <button onClick={() => remove(s)} className="ml-auto flex items-center gap-1.5 text-[11px] text-slate-600 hover:text-hazard transition-colors">
                    <Trash2 size={11} /> Delete
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
