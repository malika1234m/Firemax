import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LifeBuoy, Send, CheckCircle2, Clock, AlertTriangle, BookOpen, ExternalLink, Home, ChevronDown } from 'lucide-react'
import { DOCS_URL, CHANGELOG_URL } from '../lib/homeAssistant'
import { apiFetch, apiJson } from '../lib/api'
import { useToast } from '../context/ToastContext'
import PageHeader from '../components/PageHeader'

const CATEGORIES = [
  { value: 'general',   label: 'General' },
  { value: 'billing',   label: 'Billing' },
  { value: 'detection', label: 'Home Assistant add-on' },
  { value: 'technical', label: 'Technical issue' },
  { value: 'other',     label: 'Other' },
]

// The questions customers actually ask. Detection problems are answered in
// Home Assistant, where the detection runs, so these point there.
const FAQ = [
  { q: 'Why does the website not show my cameras or alerts?',
    a: 'Your cameras, fire detection and alerts all live in Home Assistant, on your own hardware — video never leaves your building. Open the FiremeX dashboard in the Home Assistant sidebar to see them. This website manages your account, subscription and access token.' },
  { q: 'The add-on says it is on the free tier (one camera).',
    a: 'Paste your access token into the add-on\'s licence_key option and restart it. If it is already there, check your subscription is active under Plans & Billing, and that the installation is not over your plan\'s limit under Home Assistant Connection.' },
  { q: 'I reinstalled Home Assistant or moved to a new machine.',
    a: 'Install the add-on again and paste the same token. If the log says the licence is already active elsewhere, remove the old installation under Home Assistant Connection.' },
  { q: 'Does FiremeX need internet?',
    a: 'Only to download the add-on and model, and to check your token about once a day. Detection keeps running offline for up to 60 days.' },
  { q: 'How do I get a new version of the add-on?',
    a: 'Home Assistant shows an Update button on the FiremeX add-on when a new version is released. Your settings are kept.' },
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
    if (!subject.trim() || !message.trim()) { setError('Please add a subject and a few words about it.'); return }
    setSending(true)
    try {
      await apiJson('/support/complaints', { method: 'POST', body: JSON.stringify({ subject, category, message }) })
      setSubject(''); setMessage(''); setCategory('general')
      toast({ type: 'success', message: "Thanks — we've got your message and will reply here." })
      load()
    } catch (err) {
      setError(err.message || 'Failed to submit')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="max-w-5xl fade-up">
      <PageHeader title="Help & Support" subtitle="Stuck, or just curious? Start here — and if that doesn't help, write to us. A real person reads every message." />

      <div className="grid sm:grid-cols-3 gap-3 mb-6">
        <Link to="/home-assistant" className="glass-card border border-white/[0.07] rounded-xl p-4 hover:border-brand/30 transition-colors">
          <Home size={17} className="text-brand" />
          <p className="text-[13px] text-slate-200 font-medium mt-3">Setup guide</p>
          <p className="text-[11.5px] text-slate-500 mt-0.5">Install FiremeX in Home Assistant</p>
        </Link>
        <a href={DOCS_URL} target="_blank" rel="noreferrer" className="glass-card border border-white/[0.07] rounded-xl p-4 hover:border-brand/30 transition-colors">
          <BookOpen size={17} className="text-brand" />
          <p className="text-[13px] text-slate-200 font-medium mt-3 flex items-center gap-1.5">Add-on documentation <ExternalLink size={11} /></p>
          <p className="text-[11.5px] text-slate-500 mt-0.5">Every option, cameras, EZVIZ</p>
        </a>
        <a href={CHANGELOG_URL} target="_blank" rel="noreferrer" className="glass-card border border-white/[0.07] rounded-xl p-4 hover:border-brand/30 transition-colors">
          <Clock size={17} className="text-brand" />
          <p className="text-[13px] text-slate-200 font-medium mt-3 flex items-center gap-1.5">What's new <ExternalLink size={11} /></p>
          <p className="text-[11.5px] text-slate-500 mt-0.5">Changes in each add-on version</p>
        </a>
      </div>

      <div className="glass-card border border-white/[0.07] rounded-xl p-2 mb-6">
        {FAQ.map(({ q, a }) => (
          <details key={q} className="group px-4 py-3 border-b border-white/[0.04] last:border-0">
            <summary className="flex items-center justify-between gap-3 cursor-pointer list-none text-[13px] text-slate-200">
              {q}
              <ChevronDown size={14} className="text-slate-500 shrink-0 transition-transform group-open:rotate-180" />
            </summary>
            <p className="text-[12.5px] text-slate-400 mt-2 leading-relaxed">{a}</p>
          </details>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* submit form */}
        <form onSubmit={submit} className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2">
            <LifeBuoy size={14} className="text-brand" />
            <h2 className="text-[14.5px] font-semibold text-slate-100">Send us a message</h2>
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
            <input className="field" placeholder="In a few words, what's up?" value={subject} onChange={e => setSubject(e.target.value)} maxLength={200} />
          </label>
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Message</span>
            <textarea rows={5} className="field resize-none" placeholder="Tell us what happened, and what you expected. A screenshot of the add-on log helps a lot." value={message} onChange={e => setMessage(e.target.value)} maxLength={4000} />
          </label>
          <button type="submit" disabled={sending}
                  className="flex items-center gap-2 bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            <Send size={14} /> {sending ? 'Sending…' : 'Send message'}
          </button>
        </form>

        {/* history */}
        <div className="space-y-3">
          <h2 className="text-[14.5px] font-semibold text-slate-100">Your messages ({items.length})</h2>
          {items.length === 0 ? (
            <div className="glass-card border border-white/[0.06] rounded-xl p-8 text-center text-slate-600 text-sm">No messages yet. Anything you send shows up here, with our reply.</div>
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
