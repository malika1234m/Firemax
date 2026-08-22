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

  // A brand-new workspace has no cameras, no site and no agent, so the
  // Dashboard is empty and gives no hint what to do next. Send people who just
  // registered to the setup question instead — which guide is right for them
  // depends on whether they run Home Assistant, and guessing wrong costs them
  // a page of steps that do not apply. Anyone merely revisiting /signup while
  // already logged in still goes where they were headed.
  if (user) {
    const dest = justSignedUp ? '/choose-setup' : (location.state?.from ?? '/')
    return <Navigate to={dest} replace />
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (password !== confirm) { setError('Passwords do not match.'); return }
    setLoading(true)
    try {
      setJustSignedUp(true)
      await signup(orgName, name, email, password)
    } catch (err) {
      setJustSignedUp(false)
      setError(err.message || 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      heading="Create Your Account"
      subheading="Starts a private 14-day trial workspace for your company."
      footer={<>Already have an account? <Link to="/login" className="text-ember font-semibold hover:text-ember/80">Sign In</Link></>}
    >
      <form onSubmit={handleSubmit} className="space-y-3.5">
        {error && (
          <div className="flex items-center gap-2 text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">
            <AlertTriangle size={13} className="shrink-0" /> {error}
          </div>
        )}

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Company Name</span>
          <div className="relative">
            <Building2 size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input required autoFocus className="field !pl-10"
                   placeholder="Acme Fire Safety" value={orgName} onChange={e => setOrgName(e.target.value)} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Full Name</span>
          <div className="relative">
            <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input required className="field !pl-10"
                   placeholder="Jordan Soto" value={name} onChange={e => setName(e.target.value)} />
          </div>
        </label>

        <label className="space-y-1.5 block">
          <span className="text-[12px] text-slate-400 font-medium">Email Address</span>
          <div className="relative">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type="email" required className="field !pl-10"
                   placeholder="user@example.com" value={email} onChange={e => setEmail(e.target.value)} />
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
          <span className="text-[12px] text-slate-400 font-medium">Confirm Password</span>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type={showPassword ? 'text' : 'password'} required className="field !pl-10"
                   placeholder="••••••••" value={confirm} onChange={e => setConfirm(e.target.value)} />
          </div>
        </label>

        <button type="submit" disabled={loading}
                className="w-full bg-ember text-white text-sm font-semibold py-3 rounded-lg hover:bg-ember-dark disabled:opacity-40 transition-colors mt-1">
          {loading ? 'Creating Account…' : 'Create Account'}
        </button>
      </form>
    </AuthLayout>
  )
}
