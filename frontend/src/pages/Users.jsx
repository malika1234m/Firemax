import { useEffect, useState } from 'react'
import { Plus, Trash2, UserPlus, X, Users as UsersIcon, ShieldCheck, Eye } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import PageHeader from '../components/PageHeader'

const EMPTY_FORM = { name: '', email: '', password: '', role: 'operator' }
const ROLES = ['operator', 'admin']

export default function Users() {
  const { user: me } = useAuth()
  const { toast } = useToast()
  const confirm = useConfirm()
  const [users,    setUsers]    = useState([])
  const [form,     setForm]     = useState(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const load = () => apiFetch('/users/').then(r => r.ok ? r.json() : []).then(setUsers).catch(() => {})
  useEffect(() => { load() }, [])

  const field = (key) => ({
    value: form[key],
    onChange: e => setForm(f => ({ ...f, [key]: e.target.value })),
  })

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.email.trim()) { setError('Name and email are required.'); return }
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return }
    setLoading(true); setError('')
    try {
      await apiJson('/users/', { method: 'POST', body: JSON.stringify(form) })
      setForm(EMPTY_FORM)
      setShowForm(false)
      toast({ type: 'success', message: `${form.name} was added as ${form.role}.` })
      load()
    } catch (err) {
      setError(err.message || 'Failed to add user')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (u) => {
    const ok = await confirm({ title: `Remove ${u.name}?`, message: 'They will lose access immediately.', danger: true, confirmLabel: 'Remove' })
    if (!ok) return
    try {
      await apiJson(`/users/${u.user_id}`, { method: 'DELETE' })
      toast({ type: 'success', message: `${u.name} was removed.` })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Failed to delete user' })
    }
  }

  const handleRoleChange = async (u, role) => {
    try {
      await apiJson(`/users/${u.user_id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) })
      toast({ type: 'success', message: `${u.name} is now ${role}.` })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Failed to change role' })
      load()
    }
  }

  const adminCount = users.filter(u => u.role === 'admin').length
  const operatorCount = users.filter(u => u.role === 'operator').length

  return (
    <div className="max-w-6xl space-y-6 fade-up">
      <PageHeader title="Users" subtitle={`${users.length} team member${users.length !== 1 ? 's' : ''}`}>
        <button onClick={() => { setShowForm(v => !v); setError('') }}
                className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg bg-brand text-void hover:bg-brand/85 transition-colors">
          {showForm ? <><X size={14} /> Cancel</> : <><Plus size={14} /> Add User</>}
        </button>
      </PageHeader>

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Total Members" value={users.length} icon={UsersIcon} />
        <StatCard label="Admins" value={adminCount} icon={ShieldCheck} />
        <StatCard label="Operators" value={operatorCount} icon={Eye} />
      </div>

      <p className="text-[11px] text-slate-600">
        <span className="text-slate-400 font-medium">Admins</span> manage users, cameras, billing, and system settings.{' '}
        <span className="text-slate-400 font-medium">Operators</span> monitor live feeds, review incidents, and acknowledge alerts.
      </p>

      {showForm && (
        <form onSubmit={handleAdd} className="glass-card border border-white/[0.09] rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2">
            <UserPlus size={14} className="text-brand" />
            <span className="font-raj font-semibold text-[12px] tracking-[0.1em] text-slate-400 uppercase">New Team Member</span>
          </div>
          {error && <p className="text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">{error}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Name</span>
              <input className="field" placeholder="Jordan Soto" {...field('name')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Email</span>
              <input className="field" type="email" placeholder="jordan@firemex.io" {...field('email')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Temporary Password</span>
              <input className="field" type="password" placeholder="At least 8 characters" {...field('password')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Role</span>
              <select className="field select-field appearance-none capitalize" {...field('role')}>
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
          </div>
          <p className="text-[10px] text-slate-700">Share the password with them directly — they can change it later in Settings.</p>
          <button type="submit" disabled={loading}
                  className="bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            {loading ? 'Saving…' : 'Save User'}
          </button>
        </form>
      )}

      {users.length === 0 ? (
        <p className="text-slate-700 text-sm">No users added yet.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {users.map(u => (
            <div key={u.user_id} className="glass-card border border-white/[0.07] rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-brand/15 border border-brand/25 flex items-center justify-center shrink-0">
                  <span className="font-raj font-semibold text-[11px] text-brand">
                    {u.name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()}
                  </span>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] text-slate-200 font-medium truncate">
                    {u.name} {u.user_id === me?.user_id && <span className="text-slate-600 font-normal">(you)</span>}
                  </p>
                  <p className="text-[11px] text-slate-600 truncate">{u.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-2 border-t border-white/[0.05]">
                <select value={u.role} onChange={e => handleRoleChange(u, e.target.value)}
                        disabled={u.user_id === me?.user_id}
                        className="select-field-sm text-[10px] font-medium text-slate-400 bg-white/[0.04] border border-white/[0.07] rounded-md px-2 py-1 capitalize appearance-none disabled:opacity-50">
                  {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
                <button onClick={() => handleDelete(u)} disabled={u.user_id === me?.user_id}
                        className="ml-auto text-slate-700 hover:text-hazard transition-colors disabled:opacity-30 disabled:hover:text-slate-700">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, icon: Icon }) {
  return (
    <div className="glass-card rounded-xl p-4 border border-white/[0.07]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        <Icon size={14} className="text-slate-500" />
      </div>
      <p className="font-raj font-bold text-[22px] leading-none text-white">{value}</p>
    </div>
  )
}
