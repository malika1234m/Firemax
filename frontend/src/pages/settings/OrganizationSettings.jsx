import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2 } from 'lucide-react'
import { apiFetch, apiJson } from '../../lib/api'
import { useToast } from '../../context/ToastContext'

export default function OrganizationSettings() {
  const { toast } = useToast()
  const [org,  setOrg]  = useState(null)
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => apiFetch('/organizations/me').then(r => r.ok ? r.json() : null).then(o => {
    if (!o) return
    setOrg(o)
    setName(o.name)
  }).catch(() => {})
  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await apiJson('/organizations/me', { method: 'PATCH', body: JSON.stringify({ name }) })
      toast({ type: 'success', message: 'Organization profile updated.' })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Failed to save' })
    } finally {
      setSaving(false)
    }
  }

  if (!org) return null

  return (
    <div className="space-y-6 max-w-xl">
      <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-5">
        <div className="flex items-center gap-2">
          <Building2 size={13} className="text-slate-500" />
          <div>
            <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">Company Profile</h2>
            <p className="text-[11px] text-slate-600">The name shown in your sidebar and on invoices.</p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Company name</span>
            <input className="field" value={name} onChange={e => setName(e.target.value)} />
          </label>
          <button type="submit" disabled={saving}
                  className="bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </form>
      </div>

      <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-3">
        <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">Plan</h2>
        <p className="text-[12px] text-slate-500">
          Current plan: <span className="text-slate-300 font-medium capitalize">{org.plan}</span> · Status:{' '}
          <span className="text-slate-300 font-medium capitalize">{org.subscription_status}</span>
        </p>
        <Link to="/billing" className="inline-block text-[12px] text-brand hover:text-brand/80 transition-colors">
          Manage plan & usage in Billing →
        </Link>
      </div>
    </div>
  )
}
