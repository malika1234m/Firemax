import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, Clock, CreditCard, ExternalLink, FileText, Lock, Wallet } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { useOrganization } from '../context/OrganizationContext'
import PageHeader from '../components/PageHeader'
import PlanPicker, { IntervalToggle, money, planPrice } from '../components/PlanPicker'

const RANK = { free: 0, trial: 1, starter: 2, pro: 3 }

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5 border-b border-white/[0.05] last:border-0">
      <span className="text-[13px] text-slate-400">{label}</span>
      <span className="text-[13px] text-slate-200 text-right">{children}</span>
    </div>
  )
}

const date = (d) => (d ? new Date(d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—')

/**
 * Plan, payment and invoices. Plans are sold by the camera; each subscription
 * covers one Home Assistant. Card details go through Stripe — this page never
 * sees a card number.
 */
export default function Billing() {
  const { toast } = useToast()
  const confirm = useConfirm()
  const { refresh: reloadOrg } = useOrganization()
  const [searchParams, setSearchParams] = useSearchParams()
  const [status, setStatus] = useState(null)
  const [invoices, setInvoices] = useState(null)
  const [busy, setBusy] = useState(null)
  const [interval, setPeriod] = useState('month')
  const [cameras, setCameras] = useState(5)

  const load = () => {
    apiFetch('/billing/status').then(r => (r.ok ? r.json() : null)).then(s => {
      setStatus(s)
      if (s?.subscription.interval) setPeriod(s.subscription.interval)
      if (s?.subscription.plan === 'pro') setCameras(s.subscription.cameras)
    }).catch(() => {})
    apiFetch('/billing/invoices').then(r => (r.ok ? r.json() : { invoices: [] }))
      .then(d => setInvoices(d.invoices)).catch(() => setInvoices([]))
  }
  useEffect(() => { load() }, [])

  useEffect(() => {
    const checkout = searchParams.get('checkout')
    if (checkout === 'success') toast({ type: 'success', message: 'Payment received — your plan is active. Thank you!' })
    else if (checkout === 'cancelled') toast({ type: 'info', message: 'Checkout was cancelled — nothing was charged.' })
    if (checkout) { setSearchParams({}, { replace: true }); load(); reloadOrg?.() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const run = async (key, fn) => {
    setBusy(key)
    try { await fn() } catch (err) { toast({ type: 'error', message: err.message || 'Something went wrong' }) }
    setBusy(null)
  }

  if (!status) {
    return (
      <div className="max-w-6xl space-y-6 fade-up">
        <PageHeader title="Plans & Billing" subtitle="Your plan, how you pay, and what you've paid." />
        <div className="h-48 rounded-xl border border-white/[0.06] bg-white/[0.02] animate-pulse" />
      </div>
    )
  }

  const { subscription: sub, plans, usage, limits, stripe_configured: stripeOn, has_subscription: subscribed } = status
  const current = sub.plan === 'trial' ? null : sub.plan

  const checkout = (plan) => run(plan, async () => {
    const { url } = await apiJson('/billing/checkout-session', {
      method: 'POST', body: JSON.stringify({ plan, interval, cameras }),
    })
    window.location.href = url
  })

  const change = (plan) => run(plan, async () => {
    const p = plans[plan]
    const total = money(planPrice(p, interval, cameras))
    if (!await confirm({
      title: `Switch to ${p.label}${p.per_camera ? ` with ${cameras} cameras` : ''}?`,
      message: `${total} per ${interval}. Anything extra for the rest of this period is charged now; a smaller plan starts at your next renewal.`,
      confirmLabel: 'Switch plan',
    })) return
    const res = await apiJson('/billing/subscription', {
      method: 'POST', body: JSON.stringify({ plan, interval, cameras }),
    })
    toast({ type: 'success', message: res.effective === 'renewal' ? 'Done — the change starts at your next renewal.' : 'Plan changed.' })
    load()
  })

  const cancel = () => run('free', async () => {
    if (!await confirm({
      title: 'Cancel your subscription?',
      message: `Everything keeps working until ${date(sub.renews_at)}. After that FiremeX watches 1 camera. You can undo this any time before then.`,
      danger: true, confirmLabel: 'Cancel subscription',
    })) return
    await apiJson('/billing/cancel', { method: 'POST' })
    toast({ type: 'success', message: `Cancelled. Your plan stays active until ${date(sub.renews_at)}.` })
    load()
  })

  const resume = () => run('resume', async () => {
    await apiJson('/billing/resume', { method: 'POST' })
    toast({ type: 'success', message: 'Your subscription will renew as normal.' })
    load()
  })

  const portal = () => run('portal', async () => {
    const { url } = await apiJson('/billing/portal-session', { method: 'POST' })
    window.location.href = url
  })

  // What each plan card's button does depends on where the customer is now.
  const actionFor = (p) => {
    const same = current === p.plan_id && (!subscribed || sub.interval === interval)
    if (p.plan_id === 'free') {
      if (current === 'free' || sub.state === 'free') return { kind: 'current', label: 'Your plan now' }
      if (subscribed && !sub.cancel_at_period_end) return { kind: 'secondary', label: 'Cancel to Free' }
      return { kind: 'none' }
    }
    if (subscribed) {
      if (same && (!p.per_camera || cameras === sub.cameras)) return { kind: 'current' }
      return { kind: RANK[p.plan_id] >= RANK[current] ? 'primary' : 'secondary',
               label: same ? `Change to ${cameras} cameras` : `Switch to ${p.label}` }
    }
    if (!stripeOn) return { kind: 'secondary', label: 'Talk to us' }
    return { kind: 'primary', label: `Choose ${p.label}` }
  }
  const choose = (id) => {
    if (id === 'free') return cancel()
    if (!stripeOn) { window.location.href = '/support'; return }
    return subscribed ? change(id) : checkout(id)
  }

  return (
    <div className="max-w-6xl space-y-6 fade-up">
      <PageHeader title="Plans & Billing" subtitle="Your plan, how you pay, and what you've paid." />

      <StatusBanner sub={sub} onPortal={portal} onResume={resume} busy={busy} />

      <div className="grid lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] gap-5">
        <section className="glass-card border border-white/[0.07] rounded-xl p-5">
          <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100 mb-3">
            <Wallet size={14} className="text-slate-400" /> Your subscription
          </h2>
          <Row label="Plan">{sub.label}</Row>
          <Row label="Cameras">
            {usage.cameras_in_use != null ? `${usage.cameras_in_use} in use of ${sub.cameras}` : `Up to ${sub.cameras}`}
          </Row>
          <Row label="Billing">
            {sub.state === 'trial' ? 'Free trial'
              : subscribed ? `${money(planPrice(plans[sub.plan], sub.interval, sub.cameras))} per ${sub.interval}`
              : sub.plan_source === 'manual' ? 'Managed by FiremeX' : 'Free'}
          </Row>
          <Row label={sub.cancel_at_period_end ? 'Ends on' : sub.state === 'trial' ? 'Trial ends' : 'Renews on'}>
            {sub.state === 'trial' ? date(sub.trial_ends_at) : subscribed ? date(sub.renews_at) : '—'}
          </Row>
          <Row label="Home Assistant">{usage.installs} of {limits.max_installs} connected</Row>
          <Row label="Team members">{usage.users} of {limits.max_users}</Row>
        </section>

        <section className="glass-card border border-white/[0.07] rounded-xl p-5 flex flex-col">
          <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100 mb-3">
            <CreditCard size={14} className="text-slate-400" /> Payment method
          </h2>
          {status.has_billing_account && stripeOn ? (
            <>
              <p className="text-[13px] text-slate-400 leading-relaxed">
                Change your card or billing email in Stripe's secure portal.
              </p>
              <button onClick={portal} disabled={busy === 'portal'} className="btn-secondary self-start mt-4">
                {busy === 'portal' ? 'Opening…' : 'Manage card'} <ExternalLink size={13} />
              </button>
            </>
          ) : (
            <p className="text-[13px] text-slate-400 leading-relaxed">
              No card on file — the trial and the Free plan don't need one. You add a card when you choose Home or Pro.
              {!stripeOn && ' Card payments are not switched on yet; contact us to change plan.'}
            </p>
          )}
          <p className="mt-auto pt-4 text-[12px] text-slate-500 flex items-start gap-2">
            <Lock size={12} className="mt-0.5 shrink-0" />
            Cancel any time here — no fee. You keep your plan until the end of the period you paid for.
          </p>
        </section>
      </div>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-[16px] font-semibold text-white">Plans</h2>
            <p className="text-[13px] text-slate-400 mt-1">Priced by camera. Every plan covers one Home Assistant.</p>
          </div>
          <IntervalToggle interval={interval} onChange={setPeriod} />
        </div>
        <PlanPicker plans={plans} interval={interval} cameras={cameras} onCameras={setCameras}
                    actionFor={actionFor} onChoose={choose} busy={busy} />
      </section>

      <section className="glass-card border border-white/[0.07] rounded-xl p-5">
        <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100 mb-4">
          <FileText size={14} className="text-slate-400" /> Billing history
        </h2>
        {invoices === null ? (
          <div className="h-16 rounded-lg bg-white/[0.02] animate-pulse" />
        ) : invoices.length === 0 ? (
          <p className="text-[13px] text-slate-400">No payments yet. Every invoice will be listed here, newest first.</p>
        ) : (
          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-[13px] min-w-[560px]">
              <thead>
                <tr className="text-left text-[11.5px] uppercase tracking-wider text-slate-500 border-b border-white/[0.06]">
                  <th className="font-medium py-2 px-3">Date</th>
                  <th className="font-medium py-2 px-3">Description</th>
                  <th className="font-medium py-2 px-3 text-right">Amount</th>
                  <th className="font-medium py-2 px-3">Status</th>
                  <th className="font-medium py-2 px-3" />
                </tr>
              </thead>
              <tbody>
                {invoices.map(inv => (
                  <tr key={inv.id} className="border-b border-white/[0.04] last:border-0">
                    <td className="py-3 px-3 text-slate-200 whitespace-nowrap">{date(inv.created)}</td>
                    <td className="py-3 px-3 text-slate-400">
                      {inv.description || inv.number || 'FiremeX subscription'}
                      {inv.period_start && <span className="block text-[11.5px] text-slate-500">{date(inv.period_start)} – {date(inv.period_end)}</span>}
                    </td>
                    <td className="py-3 px-3 text-slate-200 text-right font-mono tabular-nums">${inv.amount_usd.toFixed(2)}</td>
                    <td className="py-3 px-1">
                      <span className={`text-[11.5px] font-medium px-2 py-0.5 rounded border capitalize
                        ${inv.status === 'paid' ? 'text-safe border-safe/25 bg-safe/10'
                          : inv.status === 'open' ? 'text-warn border-warn/25 bg-warn/10' : 'text-slate-400 border-white/[0.1]'}`}>
                        {inv.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      {inv.url && <a href={inv.url} target="_blank" rel="noreferrer" className="text-brand hover:underline">View</a>}
                      {inv.pdf && <a href={inv.pdf} target="_blank" rel="noreferrer" className="text-brand hover:underline ml-3">PDF</a>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

function StatusBanner({ sub, onPortal, onResume, busy }) {
  if (sub.state === 'trial') {
    const urgent = sub.trial_days_left <= 3
    return (
      <Banner tone={urgent ? 'warn' : 'info'} icon={Clock}
              title={`${sub.trial_days_left} day${sub.trial_days_left === 1 ? '' : 's'} left in your free trial`}
              text={`Up to ${sub.cameras} cameras until ${date(sub.trial_ends_at)}. After that FiremeX watches 1 camera unless you choose a plan below.`} />
    )
  }
  if (sub.trial_ended && sub.state === 'free') {
    return (
      <Banner tone="hazard" icon={AlertTriangle} title="Your free trial has ended"
              text="FiremeX is now watching just 1 camera. Choose Home or Pro below to watch all of them again." />
    )
  }
  if (sub.state === 'grace') {
    return (
      <Banner tone="hazard" icon={AlertTriangle} title="Your last payment didn't go through"
              text={`All your cameras keep working until ${date(sub.grace_until)} while we retry. Update your card to avoid dropping to 1 camera.`}
              action={<button onClick={onPortal} disabled={busy === 'portal'} className="btn-primary">Update card</button>} />
    )
  }
  if (sub.status === 'past_due') {
    return (
      <Banner tone="hazard" icon={AlertTriangle} title="Payment overdue — FiremeX is watching 1 camera"
              text="Update your card and everything comes back as soon as the payment goes through."
              action={<button onClick={onPortal} disabled={busy === 'portal'} className="btn-primary">Update card</button>} />
    )
  }
  if (sub.cancel_at_period_end) {
    return (
      <Banner tone="warn" icon={Clock} title={`Your plan ends on ${date(sub.renews_at)}`}
              text="You cancelled, so it won't renew. Changed your mind?"
              action={<button onClick={onResume} disabled={busy === 'resume'} className="btn-secondary">Keep my plan</button>} />
    )
  }
  return null
}

function Banner({ tone, icon: Icon, title, text, action }) {
  const tones = {
    info: 'border-live/25 bg-live/[0.05] text-live',
    warn: 'border-warn/30 bg-warn/[0.06] text-warn',
    hazard: 'border-hazard/35 bg-hazard/[0.07] text-hazard',
  }
  return (
    <div className={`rounded-xl border p-4 flex flex-wrap items-center gap-4 ${tones[tone]}`} role="status">
      <Icon size={18} className="shrink-0" />
      <div className="flex-1 min-w-[220px]">
        <p className="text-[14px] font-semibold text-white">{title}</p>
        <p className="text-[13px] text-slate-300 mt-0.5">{text}</p>
      </div>
      {action}
    </div>
  )
}

