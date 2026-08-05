import { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { Lock, Eye, EyeOff, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { apiJson } from '../lib/api'
import AuthLayout from '../components/AuthLayout'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm,  setConfirm]  = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)
  const [done,    setDone]    = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (password !== confirm) { setError('Passwords do not match.'); return }
    setLoading(true)
    try {
      await apiJson('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, new_password: password }) })
      setDone(true)
      setTimeout(() => navigate('/login'), 2000)
    } catch (err) {
      setError(err.message || 'This reset link is invalid or has expired.')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <AuthLayout heading="Invalid Link">
        <div className="flex flex-col items-center text-center gap-3 py-2">
          <div className="w-12 h-12 rounded-full bg-hazard/10 border border-hazard/20 flex items-center justify-center">
            <AlertTriangle size={20} className="text-hazard" />
          </div>
          <p className="text-[13px] text-slate-400">This password reset link is missing or malformed.</p>
          <Link to="/forgot-password" className="text-[13px] text-ember font-semibold hover:text-ember/80 mt-2">
            Request a new link
          </Link>
        </div>
      </AuthLayout>
    )
  }

  if (done) {
    return (
      <AuthLayout heading="Password Reset">
        <div className="flex flex-col items-center text-center gap-3 py-2">
          <div className="w-12 h-12 rounded-full bg-safe/10 border border-safe/30 flex items-center justify-center">
            <CheckCircle2 size={20} className="text-safe" />
          </div>
          <p className="text-[13px] text-slate-400">Your password has been changed. Redirecting to sign in…</p>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout heading="Set a New Password" subheading="Choose a new password for your account.">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">
            <AlertTriangle size={13} className="shrink-0" /> {error}
          </div>
        )}

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">New Password</span>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type={showPassword ? 'text' : 'password'} required autoFocus className="field !pl-10"
                   placeholder="At least 8 characters" value={password} onChange={e => setPassword(e.target.value)} />
            <button type="button" onClick={() => setShowPassword(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
              {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Confirm New Password</span>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type={showPassword ? 'text' : 'password'} required className="field !pl-10"
                   placeholder="••••••••" value={confirm} onChange={e => setConfirm(e.target.value)} />
          </div>
        </label>

        <button type="submit" disabled={loading}
                className="w-full bg-ember text-white text-sm font-semibold py-3 rounded-lg hover:bg-ember-dark disabled:opacity-40 transition-colors mt-2">
          {loading ? 'Saving…' : 'Reset Password'}
        </button>
      </form>
    </AuthLayout>
  )
}
