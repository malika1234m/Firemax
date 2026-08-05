import { useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { Mail, Lock, Eye, EyeOff, AlertTriangle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import AuthLayout from '../components/AuthLayout'

export default function Login() {
  const { user, login } = useAuth()
  const location = useLocation()
  const [email,       setEmail]       = useState('')
  const [password,    setPassword]    = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error,       setError]       = useState('')
  const [loading,     setLoading]     = useState(false)

  if (user) return <Navigate to={location.state?.from ?? '/'} replace />

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      heading="Sign In to Your Account"
      footer={<>Don't have an account? <Link to="/signup" className="text-ember font-semibold hover:text-ember/80">Sign Up</Link></>}
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

        <label className="space-y-1.5 block">
          <div className="flex items-center justify-between">
            <span className="text-[12px] text-slate-400 font-medium">Password</span>
            <Link to="/forgot-password" className="text-[12px] text-ember hover:text-ember/80 font-medium">Forgot Password?</Link>
          </div>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input type={showPassword ? 'text' : 'password'} required className="field !pl-10"
                   placeholder="Enter your password" value={password} onChange={e => setPassword(e.target.value)} />
            <button type="button" onClick={() => setShowPassword(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
              {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </label>

        <button type="submit" disabled={loading}
                className="w-full bg-ember text-white text-sm font-semibold py-3 rounded-lg hover:bg-ember-dark disabled:opacity-40 transition-colors mt-2">
          {loading ? 'Signing In…' : 'Sign In'}
        </button>
      </form>
    </AuthLayout>
  )
}
