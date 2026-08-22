import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, Home, Server, Check, KeyRound, RefreshCw } from 'lucide-react'
import { apiFetch, apiJson } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { useConfirm } from '../../context/ConfirmContext'
import { DEPLOYMENT_MODES, useOrganization } from '../../context/OrganizationContext'

/* Where detection runs. Changing this only changes which setup guide and which
 * pages the customer is shown — it installs nothing and tears nothing down, so
 * it is a plain switch rather than a confirm-and-migrate flow. Someone who
 * trialled the add-on and then bought dedicated hardware should be able to move
 * across without opening a support ticket. */
const MODE_CARDS = [
  {
    mode: DEPLOYMENT_MODES.HOME_ASSISTANT,
    icon: Home,
    title: 'Home Assistant add-on',
    blurb: 'Detection runs inside Home Assistant, on your hardware, using its cameras.',
    guide: '/get-started/home-assistant',
  },
  {
    mode: DEPLOYMENT_MODES.EDGE,
    icon: Server,
    title: 'FiremeX edge agent',
    blurb: 'An agent at your site connects to cameras directly and reports to this dashboard.',
    guide: '/get-started',
  },
]

export default function OrganizationSettings() {
  const { toast } = useToast()
  const confirm = useConfirm()
  // Shared org state: switching how FiremeX runs has to reach the sidebar and
  // the route guard too, not just this page.
  const { org, chooseMode, refresh } = useOrganization()
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [licence, setLicence] = useState(null)
  const [rotating, setRotating] = useState(false)

  useEffect(() => { if (org) setName(org.name) }, [org])
  useEffect(() => {
    apiFetch('/licence/me').then(r => (r.ok ? r.json() : null)).then(setLicence).catch(() => {})
  }, [])

  // Rotation has to be self-service: the key is a bearer credential pasted into
  // a config field, so sooner or later it lands in a screenshot or a support
  // thread. Existing add-ons keep running on the old key until they re-check.
  const rotateKey = async () => {
    if (!await confirm({
      title: 'Issue a new licence key?',
      message: 'The current key stops working. Every add-on using it drops to the '
             + 'one-camera free tier until you paste the new key into its Configuration tab.',
      danger: true,
      confirmLabel: 'Issue new key',
    })) return
    setRotating(true)
    try {
      setLicence(await apiJson('/licence/me/rotate', { method: 'POST' }))
      toast({ type: 'success', message: 'New licence key issued.' })
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not rotate the key' })
    } finally {
      setRotating(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await apiJson('/organizations/me', { method: 'PATCH', body: JSON.stringify({ name }) })
      toast({ type: 'success', message: 'Organization profile updated.' })
      refresh()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Failed to save' })
    } finally {
      setSaving(false)
    }
  }

  const selectMode = async (mode) => {
    if (mode === org.deployment_mode) return
    setSwitching(true)
    try {
      await chooseMode(mode)
      toast({ type: 'success', message: 'Setup guide switched.' })
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not change how FiremeX runs' })
    } finally {
      setSwitching(false)
    }
  }

  if (!org) return null

  return (
    <div className="space-y-6 max-w-xl">
      <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-5">
        <div className="flex items-center gap-2">
          <Building2 size={13} className="text-slate-500" />
          <div>
            <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">Company Profile</h2>
            <p className="text-[11px] text-slate-600">The name shown in your sidebar and on invoices.</p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <label className="space-y-1.5 block">
            <span className="text-[11px] text-slate-500 font-medium">Company name</span>
            <input className="field" value={name} onChange={e => setName(e.target.value)} />
          </label>
          <button type="submit" disabled={saving}
                  className="bg-brand text-void text-sm font-medium px-5 py-2 rounded-lg hover:bg-brand/85 disabled:opacity-40 transition-colors">
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </form>
      </div>

      <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-4">
        <div>
          <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">How FiremeX Runs</h2>
          <p className="text-[11px] text-slate-600">
            The detection model is the same either way. This decides which setup guide you see
            and which pages apply to you.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          {MODE_CARDS.map(({ mode, icon: Icon, title, blurb, guide }) => {
            const selected = org.deployment_mode === mode
            return (
              <button
                key={mode}
                type="button"
                onClick={() => selectMode(mode)}
                disabled={switching || selected}
                className={`text-left rounded-lg border p-4 transition-colors disabled:cursor-default
                  ${selected
                    ? 'border-brand/40 bg-brand/[0.06]'
                    : 'border-white/[0.07] hover:border-white/[0.14] disabled:opacity-50'}`}
              >
                <div className="flex items-center gap-2">
                  <Icon size={14} className={selected ? 'text-brand' : 'text-slate-500'} />
                  <span className="text-[12.5px] font-medium text-slate-200 flex-1">{title}</span>
                  {selected && <Check size={13} className="text-brand shrink-0" />}
                </div>
                <p className="text-[11.5px] text-slate-500 leading-relaxed mt-2">{blurb}</p>
                {selected && (
                  <Link to={guide} onClick={e => e.stopPropagation()}
                        className="inline-block text-[11.5px] text-brand hover:text-brand/80 mt-3">
                    Open the setup guide →
                  </Link>
                )}
              </button>
            )
          })}
        </div>

        {org.deployment_mode === DEPLOYMENT_MODES.UNSET && (
          <p className="text-[11.5px] text-slate-500">
            You have not chosen yet — pick the one that matches your site.
          </p>
        )}
      </div>

      <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2">
          <KeyRound size={13} className="text-slate-500" />
          <div>
            <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">Add-on Licence Key</h2>
            <p className="text-[11px] text-slate-600">
              Lifts the one-camera free tier in the Home Assistant add-on.
            </p>
          </div>
        </div>

        <code className="block font-mono text-[12px] text-slate-300 bg-black/40 border border-white/[0.07]
                         rounded-lg px-3 py-2.5 break-all">
          {licence?.licence_key ?? 'Loading…'}
        </code>

        <div className="flex items-center gap-3">
          <button type="button" onClick={rotateKey} disabled={rotating || !licence}
                  className="inline-flex items-center gap-2 text-[12px] text-slate-400 hover:text-slate-200
                             border border-white/[0.09] rounded-lg px-3 py-1.5 disabled:opacity-40
                             transition-colors">
            <RefreshCw size={12} className={rotating ? 'animate-spin' : ''} />
            {rotating ? 'Issuing…' : 'Issue new key'}
          </button>
          <p className="text-[11px] text-slate-600">
            Treat it like a password — anyone who has it can license their own install.
          </p>
        </div>
      </div>

      <div className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-3">
        <h2 className="font-raj font-semibold text-[13px] tracking-[0.08em] text-slate-400 uppercase">Plan</h2>
        <p className="text-[12px] text-slate-500">
          Current plan: <span className="text-slate-300 font-medium capitalize">{org.plan}</span> · Status:{' '}
          <span className="text-slate-300 font-medium capitalize">{org.subscription_status}</span>
        </p>
        <Link to="/billing" className="inline-block text-[12px] text-brand hover:text-brand/80 transition-colors">
          Manage plan & usage in Billing →
        </Link>
      </div>
    </div>
  )
}
