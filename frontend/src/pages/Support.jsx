import { useEffect, useState } from 'react'
import { LifeBuoy, Send, CheckCircle2, Clock, AlertTriangle } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useToast } from '../context/ToastContext'
import PageHeader from '../components/PageHeader'

const CATEGORIES = [
  { value: 'general',   label: 'General' },
  { value: 'billing',   label: 'Billing' },
  { value: 'detection', label: 'Detection / false alarms' },
  { value: 'technical', label: 'Technical issue' },
  { value: 'other',     label: 'Other' },
]

const STATUS = {
  open:        { label: 'Open',        icon: AlertTriangle, cls: 'text-hazard bg-hazard/10 border-hazard/25' },
  in_progress: { label: 'In progress', icon: Clock,         cls: 'text-warn bg-warn/10 border-warn/25' },
  resolved:    { label: 'Resolved',    icon: CheckCircle2,  cls: 'text-safe bg-safe/10 border-safe/25' },
}

export default function Support() {
  const { toast } = useToast()
  const [subject,  setSubject]  = useState('')
  const [category, setCategory] = useState('general')
  const [message,  setMessage]  = useState('')
  const [error,    setError]    = useState('')
  const [sending,  setSending]  = useState(false)
  const [items,    setItems]    = useState([])

  const load = () => apiFetch('/support/complaints').then(r => r.ok ? r.json() : []).then(setItems).catch(() => {})
  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (!subject.trim() || !message.trim()) { setError('Please add a subject and a message.'); return }
    setSending(true)
    try {
      await apiJson('/support/complaints', { method: 'POST', body: JSON.stringify({ subject, category, message }) })
      setSubject(''); setMessage(''); setCategory('general')
      toast({ type: 'success', message: 'Your message was sent to the FiremeX team.' })
      load()
    } catch (err) {
      setError(err.message || 'Failed to submit')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="max-w-5xl fade-up">
      <PageHeader title="Support" subtitle="Report an issue or ask the FiremeX team a question" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* submit form */}
        <form onSubmit={submit} className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2">
            <LifeBuoy size={14} className="text-brand" />
            <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">New Request</h2>
          </div>
          {error && <p className="text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">{error}</p>}
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Category</span>
            <select className="field select-field appearance-none" value={category} onChange={e => setCategory(e.target.value)}>
              {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </label>
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Subject</span>
            <input className="field" placeholder="Brief summary" value={subject} onChange={e => setSubject(e.target.value)} maxLength={200} />
          </label>
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Message</span>
            <textarea rows={5} className="field resize-none" placeholder="Describe the issue in detail…" value={message} onChange={e => setMessage(e.target.value)} maxLength={4000} />
          </label>
          <button type="submit" disabled={sending}
                  className="flex items-center gap-2 bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            <Send size={14} /> {sending ? 'Sending…' : 'Submit Request'}
          </button>
        </form>

        {/* history */}
        <div className="space-y-3">
          <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">Your Requests ({items.length})</h2>
          {items.length === 0 ? (
            <div className="glass-card border border-white/[0.06] rounded-xl p-8 text-center text-slate-600 text-sm">No requests yet.</div>
          ) : items.map(c => {
            const s = STATUS[c.status] || STATUS.open
            const Icon = s.icon
            return (
              <div key={c.complaint_id} className="glass-card border border-white/[0.07] rounded-xl p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13px] text-slate-200 font-medium">{c.subject}</p>
                    <p className="text-[11px] text-slate-600 mt-0.5 capitalize">{c.category} · {(c.created_at || '').slice(0, 10)}</p>
                  </div>
                  <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium rounded-md px-2 py-1 border shrink-0 ${s.cls}`}>
                    <Icon size={11} /> {s.label}
                  </span>
                </div>
                <p className="text-[12px] text-slate-400 mt-2">{c.message}</p>
                {c.staff_note && (
                  <p className="text-[12px] text-slate-300 mt-3 pt-3 border-t border-white/[0.05]">
                    <span className="text-brand font-medium">FiremeX: </span>{c.staff_note}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
