import { useEffect, useState } from 'react'
import { Building2 } from 'lucide-react'
import { apiJson } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { useOrganization } from '../../context/OrganizationContext'

export default function CompanySettings() {
  const { toast } = useToast()
  const { org, refresh } = useOrganization()
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { if (org) setName(org.name) }, [org])

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await apiJson('/organizations/me', { method: 'PATCH', body: JSON.stringify({ name }) })
      toast({ type: 'success', message: 'Saved.' })
      refresh()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Failed to save' })
    } finally {
      setSaving(false)
    }
  }

  if (!org) return null

  return (
    <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-5">
      <div className="flex items-center gap-2">
        <Building2 size={13} className="text-slate-500" />
        <div>
          <h2 className="text-[14.5px] font-semibold text-slate-100">Company</h2>
          <p className="text-[11px] text-slate-600">The name shown in your account and on invoices.</p>
        </div>
      </div>
      <form onSubmit={submit} className="space-y-4">
        <label className="space-y-1.5 block">
          <span className="text-[11px] text-slate-500 font-medium">Company name</span>
          <input className="field" value={name} onChange={e => setName(e.target.value)} />
        </label>
        <button type="submit" disabled={saving || !name.trim()}
                className="bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
          {saving ? 'Saving…' : 'Save'}
        </button>
      </form>
    </div>
  )
}
