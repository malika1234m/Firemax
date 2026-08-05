import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Mail, AlertTriangle, MailCheck } from 'lucide-react'
import { apiJson } from '../lib/api'
import AuthLayout from '../components/AuthLayout'

export default function ForgotPassword() {
  const [email,   setEmail]   = useState('')
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)
  const [sent,    setSent]    = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await apiJson('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) })
      setSent(true)
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <AuthLayout heading="Check Your Email">
        <div className="flex flex-col items-center text-center gap-3 py-2">
          <div className="w-12 h-12 rounded-full bg-ember/10 border border-ember/20 flex items-center justify-center">
            <MailCheck size={20} className="text-ember" />
          </div>
          <p className="text-[13px] text-slate-400">
            If an account exists for <span className="font-medium text-slate-800">{email}</span>, a password
            reset link is on its way. It expires in 1 hour.
          </p>
          <Link to="/login" className="text-[13px] text-ember font-semibold hover:text-ember/80 mt-2">
            Back to Sign In
          </Link>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      heading="Forgot Password?"
      subheading="Enter your email and we'll send you a reset link."
      footer={<>Remembered it? <Link to="/login" className="text-ember font-semibold hover:text-ember/80">Sign In</Link></>}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">
            <AlertTriangle size={13} className="shrink-0" /> {error}
          </div>
        )}

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Email Address</span>
          <div className="relative">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type="email" required autoFocus className="field !pl-10"
                   placeholder="user@example.com" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
        </label>

        <button type="submit" disabled={loading}
                className="w-full bg-ember text-white text-sm font-semibold py-3 rounded-lg hover:bg-ember-dark disabled:opacity-40 transition-colors mt-2">
          {loading ? 'Sending…' : 'Send Reset Link'}
        </button>
      </form>
    </AuthLayout>
  )
}
