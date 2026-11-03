import { useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { Mail, Lock, User, Building2, Eye, EyeOff, AlertTriangle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AuthLayout from '../components/AuthLayout'

export default function Signup() {
  const { user, signup } = useAuth()
  const location = useLocation()
  const [orgName,  setOrgName]  = useState('')
  const [name,     setName]     = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [confirm,  setConfirm]  = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [justSignedUp, setJustSignedUp] = useState(false)

  // Someone who has just registered goes straight into first-time setup —
  // plan, token, Home Assistant. Anyone merely revisiting /signup while
  // already signed in still goes where they were headed.
  if (user) {
    const dest = justSignedUp ? '/welcome' : (location.state?.from ?? '/')
    return <Navigate to={dest} replace />
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) { setError('Please use at least 8 characters for your password.'); return }
    if (password !== confirm) { setError("Those two passwords don't match — try typing them again."); return }
    setLoading(true)
    try {
      setJustSignedUp(true)
      await signup(orgName, name, email, password)
    } catch (err) {
      setJustSignedUp(false)
      setError(err.message || "We couldn't create your account just now. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      heading="Create your account"
      subheading="Free for 14 days, no card needed. It takes about a minute."
      footer={<>Already have an account? <Link to="/login" className="text-ember font-semibold hover:text-ember/80">Sign in</Link></>}
    >
      <form onSubmit={handleSubmit} className="space-y-3.5">
        {error && (
          <div className="flex items-center gap-2 text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">
            <AlertTriangle size={13} className="shrink-0" /> {error}
          </div>
        )}

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Company name</span>
          <div className="relative">
            <Building2 size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input required autoFocus className="field !pl-10"
                   placeholder="Acme Fire Safety" value={orgName} onChange={e => setOrgName(e.target.value)} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Your name</span>
          <div className="relative">
            <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input required className="field !pl-10"
                   placeholder="Jordan Soto" value={name} onChange={e => setName(e.target.value)} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Email</span>
          <div className="relative">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type="email" required className="field !pl-10"
                   placeholder="you@company.com" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Password</span>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type={showPassword ? 'text' : 'password'} required className="field !pl-10"
                   placeholder="At least 8 characters" value={password} onChange={e => setPassword(e.target.value)} />
            <button type="button" onClick={() => setShowPassword(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
              {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Confirm password</span>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type={showPassword ? 'text' : 'password'} required className="field !pl-10"
                   placeholder="••••••••" value={confirm} onChange={e => setConfirm(e.target.value)} />
          </div>
        </label>

        <button type="submit" disabled={loading}
                className="w-full bg-ember text-white text-sm font-semibold py-3 rounded-lg hover:bg-ember-dark disabled:opacity-40 transition-colors mt-1">
          {loading ? 'Setting up your account…' : 'Create my account'}
        </button>
      </form>
    </AuthLayout>
  )
}
