import { useEffect, useState } from 'react'
import { Plus, Trash2, CalendarClock, Clock, UserCheck } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import PageHeader from '../components/PageHeader'

const EMPTY_FORM = { user_id: '', start_time: '', end_time: '', label: '', notes: '' }

export default function Shifts() {
  const { isAdmin } = useAuth()
  const { toast } = useToast()
  const confirm = useConfirm()
  const [shifts,   setShifts]   = useState([])
  const [users,    setUsers]    = useState([])
  const [form,     setForm]     = useState(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const load = () => apiFetch('/shifts/').then(r => r.ok ? r.json() : []).then(setShifts).catch(() => {})
  useEffect(() => {
    load()
    if (isAdmin) apiFetch('/users/').then(r => r.ok ? r.json() : []).then(users => {
      setUsers(users)
      setForm(f => ({ ...f, user_id: f.user_id || users[0]?.user_id || '' }))
    }).catch(() => {})
  }, [isAdmin])

  const field = (key) => ({
    value: form[key],
    onChange: e => setForm(f => ({ ...f, [key]: e.target.value })),
  })

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.user_id || !form.start_time || !form.end_time) { setError('Operator, start, and end time are required.'); return }
    setLoading(true); setError('')
    try {
      await apiJson('/shifts/', { method: 'POST', body: JSON.stringify(form) })
      setForm(f => ({ ...EMPTY_FORM, user_id: f.user_id }))
      setShowForm(false)
      toast({ type: 'success', message: 'Shift assigned.' })
      load()
    } catch (err) {
      setError(err.message || 'Failed to create shift')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    const ok = await confirm({ title: 'Remove this shift?', danger: true, confirmLabel: 'Remove' })
    if (!ok) return
    await apiFetch(`/shifts/${id}`, { method: 'DELETE' })
    toast({ type: 'success', message: 'Shift removed.' })
    load()
  }

  const now = Date.now()
  const upcoming = shifts.filter(s => new Date(s.end_time).getTime() >= now)
  const past     = shifts.filter(s => new Date(s.end_time).getTime() < now)
  const onShift  = shifts.filter(s => new Date(s.start_time).getTime() <= now && new Date(s.end_time).getTime() >= now)

  return (
    <div className="max-w-6xl space-y-6 fade-up">
      <PageHeader title="Shifts" subtitle={isAdmin ? 'Assign operator working hours' : 'Your assigned shifts'}>
        {isAdmin && (
          <button onClick={() => { setShowForm(v => !v); setError('') }}
                  className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg bg-brand text-void hover:bg-brand/85 transition-colors">
            <Plus size={14} /> Assign Shift
          </button>
        )}
      </PageHeader>

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="On Shift Now" value={onShift.length} icon={UserCheck} tone={onShift.length > 0 ? 'safe' : undefined} />
        <StatCard label="Upcoming" value={upcoming.length} icon={Clock} />
        <StatCard label="Total Scheduled" value={shifts.length} icon={CalendarClock} />
      </div>

      {showForm && isAdmin && (
        <form onSubmit={handleAdd} className="glass-card border border-white/[0.09] rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2">
            <CalendarClock size={14} className="text-brand" />
            <span className="font-raj font-semibold text-[12px] tracking-[0.1em] text-slate-400 uppercase">New Shift</span>
          </div>
          {error && <p className="text-xs text-hazard bg-hazard/10 border border-hazard/20 rounded-lg px-3 py-2.5">{error}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Operator</span>
              <select className="field select-field appearance-none" {...field('user_id')}>
                {users.map(u => <option key={u.user_id} value={u.user_id}>{u.name} ({u.role})</option>)}
              </select>
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Label</span>
              <input className="field" placeholder="Morning / Night / Weekend" {...field('label')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Start</span>
              <input type="datetime-local" className="field" {...field('start_time')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">End</span>
              <input type="datetime-local" className="field" {...field('end_time')} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Notes <span className="text-slate-700">(optional)</span></span>
              <input className="field" placeholder="Coverage notes" {...field('notes')} />
            </label>
          </div>
          <button type="submit" disabled={loading}
                  className="bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            {loading ? 'Saving…' : 'Save Shift'}
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <ShiftList title="Upcoming" shifts={upcoming} isAdmin={isAdmin} onDelete={handleDelete} onShift={onShift} />
        <ShiftList title="Past" shifts={past} isAdmin={isAdmin} onDelete={handleDelete} onShift={onShift} dim />
      </div>
    </div>
  )
}

function StatCard({ label, value, icon: Icon, tone }) {
  return (
    <div className="glass-card rounded-xl p-4 border border-white/[0.07]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        <Icon size={14} className={tone === 'safe' ? 'text-safe' : 'text-slate-500'} />
      </div>
      <p className={`font-raj font-bold text-[22px] leading-none ${tone === 'safe' ? 'text-safe' : 'text-white'}`}>{value}</p>
    </div>
  )
}

function ShiftList({ title, shifts, isAdmin, onDelete, onShift, dim }) {
  return (
    <div className="space-y-2">
      <h2 className="font-raj font-semibold text-[12px] tracking-[0.1em] text-slate-500 uppercase">{title}</h2>
      {shifts.length === 0 ? (
        <p className="text-slate-700 text-sm">No shifts here.</p>
      ) : shifts.map(s => {
        const isLive = onShift.some(o => o.shift_id === s.shift_id)
        return (
          <div key={s.shift_id} className={`glass-card border rounded-xl px-4 py-3 flex items-center gap-3
            ${isLive ? 'border-safe/30' : 'border-white/[0.07]'} ${dim ? 'opacity-50' : ''}`}>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] text-slate-200 font-medium truncate flex items-center gap-2">
                {s.user_name} {s.label && <span className="text-slate-500 font-normal">· {s.label}</span>}
                {isLive && <span className="text-[9px] font-raj font-bold tracking-widest uppercase bg-safe/15 text-safe px-1.5 py-0.5 rounded">Live</span>}
              </p>
              <p className="text-[11px] text-slate-600">
                {new Date(s.start_time).toLocaleString()} — {new Date(s.end_time).toLocaleString()}
              </p>
              {s.notes && <p className="text-[11px] text-slate-700 mt-0.5">{s.notes}</p>}
            </div>
            {isAdmin && (
              <button onClick={() => onDelete(s.shift_id)} className="text-slate-700 hover:text-hazard transition-colors shrink-0">
                <Trash2 size={13} />
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
