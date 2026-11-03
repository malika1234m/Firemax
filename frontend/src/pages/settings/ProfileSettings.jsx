import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Lock } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { apiJson } from '../../lib/api'
import { roleLabel } from '../../lib/format'

export default function ProfileSettings() {
  return <ProfileCard />
}

/* Password and signing out. Alert channels (SMS, push) used to live beside
 * these; alerts now come from Home Assistant, so they are set up there. */
export function SecuritySettings() {
  return <ChangePasswordCard />
}

function ProfileCard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const initials = user?.name?.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase() ?? '?'

  return (
    <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-4">
      <h2 className="text-[14.5px] font-semibold text-slate-100">Your profile</h2>
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-full bg-brand/15 border border-brand/25 flex items-center justify-center shrink-0">
          <span className="font-raj font-semibold text-[14px] text-brand">{initials}</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[14px] text-slate-200 font-medium truncate">{user?.name}</p>
          <p className="text-[12px] text-slate-600 truncate">{user?.email}</p>
        </div>
        <span className="text-[10px] font-medium text-brand bg-brand/10 border border-brand/20 rounded-md px-2.5 py-1 capitalize shrink-0">
          {roleLabel(user?.role)}
        </span>
      </div>
      <button onClick={handleLogout}
              className="flex items-center gap-2 text-[12px] text-slate-500 hover:text-hazard transition-colors">
        <LogOut size={13} /> Sign out
      </button>
    </div>
  )
}

function ChangePasswordCard() {
  const { toast } = useToast()
  const [current, setCurrent] = useState('')
  const [next,    setNext]    = useState('')
  const [confirm, setConfirm] = useState('')
  const [error,   setError]   = useState('')
  const [saving,  setSaving]  = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (next.length < 8) { setError('Please use at least 8 characters for your new password.'); return }
    if (next !== confirm) { setError("The two new passwords don't match — try typing them again."); return }
    setSaving(true)
    try {
      await apiJson('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: next }),
      })
      setCurrent(''); setNext(''); setConfirm('')
      toast({ type: 'success', message: 'Done — your password is changed.' })
    } catch (err) {
      setError(err.message || 'Failed to change password')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Lock size={13} className="text-slate-500" />
        <div>
          <h2 className="text-[14.5px] font-semibold text-slate-100">Password</h2>
          <p className="text-[11px] text-slate-600">Change the password used to sign in.</p>
        </div>
      </div>
      {error && <p className="text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">{error}</p>}
      <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <label className="space-y-1.5">
          <span className="text-[11px] text-slate-500 font-medium">Current password</span>
          <input type="password" className="field" value={current} onChange={e => setCurrent(e.target.value)} placeholder="••••••••" />
        </label>
        <label className="space-y-1.5">
          <span className="text-[11px] text-slate-500 font-medium">New password</span>
          <input type="password" className="field" value={next} onChange={e => setNext(e.target.value)} placeholder="At least 8 characters" />
        </label>
        <label className="space-y-1.5">
          <span className="text-[11px] text-slate-500 font-medium">Confirm new password</span>
          <input type="password" className="field" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="••••••••" />
        </label>
        <div className="sm:col-span-3">
          <button type="submit" disabled={saving || !current || !next}
                  className="bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            {saving ? 'Saving…' : 'Change password'}
          </button>
        </div>
      </form>
    </div>
  )
}
