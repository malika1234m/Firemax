import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldAlert, Lock, Mail, AlertTriangle } from 'lucide-react'
import { apiFetch, apiJson } from '../../lib/api'

export default function PlatformLogin() {
  const navigate = useNavigate()
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  // If already authenticated as platform admin, skip to the console.
  useEffect(() => {
    apiFetch('/platform/auth/me').then(r => { if (r.ok) navigate('/platform', { replace: true }) }).catch(() => {})
  }, [navigate])

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await apiJson('/platform/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      navigate('/platform', { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-void flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-xl bg-slate-900 border border-white/[0.08] flex items-center justify-center">
            <ShieldAlert size={22} className="text-slate-400" />
          </div>
          <div className="text-center">
            <h1 className="font-raj font-bold text-[18px] text-white">FiremeX Platform</h1>
            <p className="text-[11px] font-medium tracking-[0.15em] uppercase text-slate-600 mt-0.5">Internal Ops Console</p>
          </div>
        </div>

        <form onSubmit={submit} className="glass-card border border-white/[0.09] rounded-xl p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-2 text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">
              <AlertTriangle size={13} className="shrink-0" /> {error}
            </div>
          )}
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Email</span>
            <div className="relative">
              <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 pointer-events-none" />
              <input type="email" required autoFocus className="field !pl-10" placeholder="ops@firemex.io"
                     value={email} onChange={e => setEmail(e.target.value)} />
            </div>
          </label>
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Password</span>
            <div className="relative">
              <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 pointer-events-none" />
              <input type="password" required className="field !pl-10" placeholder="••••••••"
                     value={password} onChange={e => setPassword(e.target.value)} />
            </div>
          </label>
          <button type="submit" disabled={loading}
                  className="w-full bg-slate-200 text-void text-sm font-semibold py-2.5 rounded-lg hover:bg-white disabled:opacity-40 transition-colors">
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
        <p className="text-center text-[11px] text-slate-700 mt-4">Restricted to FiremeX staff. Access is monitored.</p>
      </div>
    </div>
  )
}
