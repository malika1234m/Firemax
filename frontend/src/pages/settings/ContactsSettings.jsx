import { useEffect, useState } from 'react'
import { Plus, Trash2, PhoneCall } from 'lucide-react'
import { apiFetch, apiJson } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { useConfirm } from '../../context/ConfirmContext'

const CONTACT_EMPTY = { name: '', phone: '', notify_via: 'sms' }

export default function ContactsSettings() {
  const { toast } = useToast()
  const confirm = useConfirm()
  const [contacts, setContacts] = useState([])
  const [form,     setForm]     = useState(CONTACT_EMPTY)
  const [showForm, setShowForm] = useState(false)
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const load = () => apiFetch('/authorities/').then(r => r.ok ? r.json() : []).then(setContacts).catch(() => {})
  useEffect(() => { load() }, [])

  const field = (key) => ({
    value: form[key],
    onChange: e => setForm(f => ({ ...f, [key]: e.target.value })),
  })

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.phone.trim()) { setError('Name and phone number are required.'); return }
    setLoading(true); setError('')
    try {
      await apiJson('/authorities/', { method: 'POST', body: JSON.stringify(form) })
      setForm(CONTACT_EMPTY)
      setShowForm(false)
      toast({ type: 'success', message: `${form.name} added to authority contacts.` })
      load()
    } catch (err) {
      setError(err.message || 'Failed to add contact')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    const ok = await confirm({ title: 'Remove this contact?', danger: true, confirmLabel: 'Remove' })
    if (!ok) return
    await apiFetch(`/authorities/${id}`, { method: 'DELETE' })
    toast({ type: 'success', message: 'Contact removed.' })
    load()
  }

  return (
    <div className="max-w-2xl glass-card border border-white/[0.07] rounded-xl p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">
            Authority Contacts
          </h2>
          <p className="text-[11px] text-slate-600 mt-0.5">
            Called/texted via Twilio the moment an operator confirms an incident (not on raw detections).
          </p>
        </div>
        <button onClick={() => { setShowForm(v => !v); setError('') }}
                className="flex items-center gap-1.5 text-[11px] font-medium text-brand border border-brand/30 rounded-lg px-3 py-1.5 hover:bg-brand/10 transition-colors shrink-0">
          <Plus size={12} /> Add
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleAdd} className="border border-white/[0.07] rounded-lg p-4 space-y-3">
          {error && <p className="text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">{error}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Name</span>
              <input className="field" placeholder="Fire Dept — Station 4" {...field('name')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Phone (E.164 format)</span>
              <input className="field font-mono text-xs" placeholder="+15551234567" {...field('phone')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Notify via</span>
              <select className="field select-field appearance-none" {...field('notify_via')}>
                <option value="sms">SMS</option>
                <option value="call">Call</option>
                <option value="both">Both</option>
              </select>
            </label>
          </div>
          <button type="submit" disabled={loading}
                  className="bg-brand text-void text-sm font-medium px-4 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            {loading ? 'Saving…' : 'Save Contact'}
          </button>
        </form>
      )}

      <div className="space-y-2">
        {contacts.length === 0 ? (
          <p className="text-slate-700 text-sm">No authority contacts configured yet.</p>
        ) : contacts.map(c => (
          <div key={c.contact_id} className="flex items-center gap-3 border border-white/[0.06] rounded-lg px-3 py-2.5">
            <PhoneCall size={13} className="text-slate-600 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-[12px] text-slate-200 font-medium truncate">{c.name}</p>
              <p className="text-[11px] font-mono text-slate-600 truncate">{c.phone}</p>
            </div>
            <span className="text-[10px] font-medium text-slate-400 bg-white/[0.04] border border-white/[0.07] rounded-md px-2 py-1 uppercase shrink-0">
              {c.notify_via}
            </span>
            <button onClick={() => handleDelete(c.contact_id)} className="text-slate-700 hover:text-hazard transition-colors shrink-0">
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
