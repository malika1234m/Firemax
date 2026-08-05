import { useState } from 'react'
import { Link } from 'react-router-dom'
import { User, Mail, Building2, Phone, MessageSquare, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { apiJson } from '../lib/api'
import AuthLayout from '../components/AuthLayout'

const EMPTY = { name: '', email: '', company: '', phone: '', message: '' }

export default function RequestDemo() {
  const [form,    setForm]    = useState(EMPTY)
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)
  const [sent,    setSent]    = useState(false)

  const field = (key) => ({
    value: form[key],
    onChange: e => setForm(f => ({ ...f, [key]: e.target.value })),
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await apiJson('/demo-requests/', {
        method: 'POST',
        body: JSON.stringify({
          name: form.name, email: form.email, company: form.company,
          phone: form.phone || undefined, message: form.message || undefined,
        }),
      })
      setSent(true)
    } catch (err) {
      setError(err.message || 'Something went wrong — please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <AuthLayout heading="Request Received">
        <div className="flex flex-col items-center text-center gap-3 py-2">
          <div className="w-12 h-12 rounded-full bg-safe/10 border border-safe/30 flex items-center justify-center">
            <CheckCircle2 size={20} className="text-safe" />
          </div>
          <p className="text-[13px] text-slate-400">
            Thanks, {form.name.split(' ')[0]} — someone from our team will reach out to{' '}
            <span className="text-slate-200 font-medium">{form.email}</span> shortly to set up your demo.
          </p>
          <Link to="/" className="text-[13px] text-ember font-semibold hover:text-ember/80 mt-2">
            Back to Home
          </Link>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      heading="Request a Demo"
      subheading="Tell us about your team and we'll walk you through FiremeX."
      footer={<>Rather explore it yourself? <Link to="/signup" className="text-ember font-semibold hover:text-ember/80">Start a free trial</Link></>}
    >
      <form onSubmit={handleSubmit} className="space-y-3.5">
        {error && (
          <div className="flex items-center gap-2 text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">
            <AlertTriangle size={13} className="shrink-0" /> {error}
          </div>
        )}

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Full Name</span>
          <div className="relative">
            <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input required autoFocus className="field !pl-10" placeholder="Jordan Soto" {...field('name')} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Work Email</span>
          <div className="relative">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type="email" required className="field !pl-10" placeholder="you@company.com" {...field('email')} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Company</span>
          <div className="relative">
            <Building2 size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input required className="field !pl-10" placeholder="Acme Fire Safety" {...field('company')} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Phone <span className="text-slate-600">(optional)</span></span>
          <div className="relative">
            <Phone size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input className="field !pl-10" placeholder="+1 555 123 4567" {...field('phone')} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">What are you looking to monitor? <span className="text-slate-600">(optional)</span></span>
          <div className="relative">
            <MessageSquare size={15} className="absolute left-3 top-3 text-slate-500 pointer-events-none" />
            <textarea rows={3} className="field !pl-10 resize-none" placeholder="e.g. a 3-building warehouse campus"
                      {...field('message')} />
          </div>
        </label>

        <button type="submit" disabled={loading}
                className="w-full bg-ember text-white text-sm font-semibold py-3 rounded-lg hover:bg-ember-dark disabled:opacity-40 transition-colors mt-1">
          {loading ? 'Sending…' : 'Request Demo'}
        </button>
      </form>
    </AuthLayout>
  )
}
