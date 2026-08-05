import { useEffect, useState } from 'react'
import { Home, Link2, KeyRound, CheckCircle2, XCircle, Trash2, Info } from 'lucide-react'
import { apiFetch, apiJson } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { useConfirm } from '../../context/ConfirmContext'

export default function HomeAssistantSettings() {
  const { toast } = useToast()
  const confirm = useConfirm()
  const [cfg,     setCfg]     = useState(null)
  const [url,     setUrl]     = useState('')
  const [token,   setToken]   = useState('')
  const [saving,  setSaving]  = useState(false)
  const [error,   setError]   = useState('')

  const load = () => apiFetch('/ha/config').then(r => r.ok ? r.json() : null).then(c => {
    if (!c) return
    setCfg(c)
    setUrl(c.ha_url || '')
  }).catch(() => {})
  useEffect(() => { load() }, [])

  const save = async (e) => {
    e.preventDefault()
    setError('')
    if (!token.trim()) { setError('Enter a Home Assistant long-lived access token to save.'); return }
    setSaving(true)
    try {
      await apiJson('/ha/config', { method: 'PUT', body: JSON.stringify({ ha_url: url.trim(), ha_token: token.trim() }) })
      setToken('')
      toast({ type: 'success', message: 'Home Assistant connected.' })
      load()
    } catch (err) {
      setError(err.message || 'Failed to save Home Assistant settings')
    } finally {
      setSaving(false)
    }
  }

  const disconnect = async () => {
    const ok = await confirm({ title: 'Disconnect Home Assistant?', message: 'Device control and automations will stop until reconnected.', danger: true, confirmLabel: 'Disconnect' })
    if (!ok) return
    await apiFetch('/ha/config', { method: 'DELETE' })
    setToken(''); setUrl('')
    toast({ type: 'success', message: 'Home Assistant disconnected.' })
    load()
  }

  if (!cfg) return null

  return (
    <div className="max-w-xl space-y-6">
      <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Home size={13} className="text-slate-500" />
            <div>
              <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">Home Assistant</h2>
              <p className="text-[11px] text-slate-600">Connect your organization's own Home Assistant to control devices on confirmed incidents.</p>
            </div>
          </div>
          <span className={`flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-lg border shrink-0
            ${cfg.configured ? 'bg-safe/10 text-safe border-safe/25' : 'bg-white/[0.04] text-slate-500 border-white/[0.08]'}`}>
            {cfg.configured ? <><CheckCircle2 size={12} /> Connected</> : <><XCircle size={12} /> Not connected</>}
          </span>
        </div>

        {!cfg.encryption_available && (
          <p className="text-[12px] text-warn bg-warn/[0.06] border border-warn/25 rounded-lg px-3 py-2.5">
            Secret encryption isn't configured on this server, so credentials can't be stored securely yet.
            Set <code className="font-mono">SECRETS_ENCRYPTION_KEY</code> in backend/.env.
          </p>
        )}

        {error && <p className="text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">{error}</p>}

        <form onSubmit={save} className="space-y-4">
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Home Assistant URL</span>
            <div className="relative">
              <Link2 size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
              <input className="field !pl-10" placeholder="https://your-home.ui.nabu.casa" value={url}
                     onChange={e => setUrl(e.target.value)} />
            </div>
            <span className="text-[10px] text-slate-700 block">Your HA must be reachable from the internet — e.g. a Nabu Casa cloud URL or an HTTPS endpoint you expose.</span>
          </label>

          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">
              Long-Lived Access Token {cfg.configured && <span className="text-slate-700">(leave blank to keep current)</span>}
            </span>
            <div className="relative">
              <KeyRound size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
              <input type="password" className="field !pl-10" placeholder={cfg.configured ? '••••••••••••' : 'Paste token from HA → Profile → Security'}
                     value={token} onChange={e => setToken(e.target.value)} />
            </div>
            <span className="text-[10px] text-slate-700 flex items-start gap-1.5">
              <Info size={11} className="shrink-0 mt-0.5" />
              Stored encrypted at rest and never shown again after saving.
            </span>
          </label>

          <div className="flex items-center gap-3">
            <button type="submit" disabled={saving || !cfg.encryption_available}
                    className="bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
              {saving ? 'Saving…' : cfg.configured ? 'Update Connection' : 'Connect'}
            </button>
            {cfg.configured && (
              <button type="button" onClick={disconnect}
                      className="flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-hazard transition-colors">
                <Trash2 size={13} /> Disconnect
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
