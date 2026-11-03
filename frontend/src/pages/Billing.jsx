import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CreditCard, ExternalLink, CheckCircle2, Sparkles, Rocket, Crown, FileText, Wallet } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useToast } from '../context/ToastContext'
import PageHeader from '../components/PageHeader'

const PLAN_ORDER = ['trial', 'starter', 'pro']
const PLAN_ICON = { trial: Sparkles, starter: Rocket, pro: Crown }

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2 border-b border-white/[0.04] last:border-0">
      <span className="text-[12.5px] text-slate-500">{label}</span>
      <span className="text-[12.5px] text-slate-200 text-right">{children}</span>
    </div>
  )
}

/**
 * Plan, payment method and invoices. Card details, plan changes and
 * cancelling go through Stripe's billing portal — the website never sees a
 * card number.
 */
export default function Billing() {
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [status, setStatus] = useState(null)
  const [invoices, setInvoices] = useState(null)
  const [busy, setBusy] = useState(null)

  const load = () => {
    apiFetch('/billing/status').then(r => (r.ok ? r.json() : null)).then(setStatus).catch(() => {})
    apiFetch('/billing/invoices').then(r => (r.ok ? r.json() : { invoices: [] }))
      .then(d => setInvoices(d.invoices)).catch(() => setInvoices([]))
  }
  useEffect(() => { load() }, [])

  useEffect(() => {
    const checkout = searchParams.get('checkout')
    if (checkout === 'success') {
      toast({ type: 'success', message: 'Subscription active — thank you!' })
      load()
    } else if (checkout === 'cancelled') {
      toast({ type: 'info', message: 'Checkout was cancelled — no changes made.' })
    }
    if (checkout) setSearchParams({}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const checkout = async (plan) => {
    setBusy(plan)
    try {
      const { url } = await apiJson('/billing/checkout-session', { method: 'POST', body: JSON.stringify({ plan }) })
      window.location.href = url
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not start checkout' })
      setBusy(null)
    }
  }

  const portal = async () => {
    setBusy('portal')
    try {
      const { url } = await apiJson('/billing/portal-session', { method: 'POST' })
      window.location.href = url
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not open the billing portal' })
      setBusy(null)
    }
  }

  if (!status) return <div className="max-w-6xl fade-up"><PageHeader title="Plans & Billing" subtitle="Your plan, how you pay, and past invoices." /></div>

  const { org, usage, limits, plans, stripe_configured: stripeConfigured, has_billing_account: hasAccount } = status
  const trialDays = org.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(org.trial_ends_at) - Date.now()) / 86400_000)) : null
  const nextBilling = org.plan === 'trial'
    ? (trialDays > 0 ? `Trial ends in ${trialDays} day${trialDays === 1 ? '' : 's'}` : 'Trial ended')
    : org.current_period_end ? new Date(org.current_period_end).toLocaleDateString()
    : org.plan_source === 'manual' ? 'Managed by FiremeX' : 'Not scheduled'
  // Once there is a paid subscription, upgrades and downgrades are changes to
  // it (prorated by Stripe), not a second checkout.
  const subscribed = hasAccount && org.plan !== 'trial'
  const rank = (p) => PLAN_ORDER.indexOf(p)

  return (
    <div className="max-w-6xl space-y-6 fade-up">
      <PageHeader title="Plans & Billing" subtitle="Your plan, how you pay, and past invoices." />

      <div className="grid lg:grid-cols-2 gap-5">
        <section className="glass-card border border-white/[0.07] rounded-xl p-5">
          <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100 mb-4">
            <Wallet size={14} className="text-slate-500" /> Your subscription
          </h2>
          <Row label="Current plan">{limits.label}</Row>
          <Row label="Status"><span className="capitalize">{org.subscription_status}</span></Row>
          <Row label="Billing interval">{org.plan === 'trial' ? 'Free trial' : 'Monthly'}</Row>
          <Row label="Next billing date">{nextBilling}</Row>
          <Row label="Home Assistant installations">{usage.installs} of {limits.max_installs}</Row>
          <Row label="Team members">{usage.users} of {limits.max_users}</Row>
        </section>

        <section className="glass-card border border-white/[0.07] rounded-xl p-5 flex flex-col">
          <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100 mb-4">
            <CreditCard size={14} className="text-slate-500" /> Payment method
          </h2>
          {hasAccount && stripeConfigured ? (
            <>
              <p className="text-[12.5px] text-slate-400 leading-relaxed">
                Update your card, download receipts, change or cancel your plan in the secure billing portal.
              </p>
              <button onClick={portal} disabled={busy === 'portal'}
                      className="mt-4 self-start inline-flex items-center gap-1.5 text-[12.5px] font-medium text-brand border border-brand/30 rounded-lg px-3.5 py-2 hover:bg-brand/10 disabled:opacity-40 transition-colors">
                {busy === 'portal' ? 'Opening…' : 'Manage payment method'} <ExternalLink size={12} />
              </button>
            </>
          ) : (
            <p className="text-[12.5px] text-slate-500 leading-relaxed">
              No card on file. You add one when you choose a paid plan — the free trial needs none.
              {!stripeConfigured && ' Card payments are not switched on yet; contact us to change plan.'}
            </p>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {PLAN_ORDER.filter(p => plans[p]).map(plan => {
          const p = plans[plan]
          const current = org.plan === plan
          const Icon = PLAN_ICON[plan]
          const up = rank(plan) > rank(org.plan)
          return (
            <div key={plan} className={`glass-card rounded-xl p-5 border flex flex-col gap-4
              ${current ? 'border-brand/40' : 'border-white/[0.07]'}`}>
              <div className="flex items-center gap-2.5">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0
                  ${current ? 'bg-brand/15 text-brand' : 'bg-white/[0.04] text-slate-500'}`}>
                  <Icon size={16} />
                </div>
                <div>
                  <p className="font-raj font-semibold text-[15px] text-white">{p.label}</p>
                  <p className="font-raj font-bold text-[22px] text-white leading-none mt-0.5">
                    {p.amount_usd ? `$${p.amount_usd}` : 'Free'}
                    {p.amount_usd ? <span className="text-[11px] text-slate-600 font-normal">/month</span> : null}
                  </p>
                </div>
              </div>
              <p className="text-[11.5px] text-slate-500 pb-3 border-b border-white/[0.06]">
                {p.max_installs} Home Assistant installation{p.max_installs === 1 ? '' : 's'} · {p.max_users} team members
              </p>
              <ul className="space-y-2 text-[12px] text-slate-400 flex-1">
                {p.features.map(f => (
                  <li key={f} className="flex items-start gap-2">
                    <CheckCircle2 size={13} className="text-brand shrink-0 mt-0.5" /> {f}
                  </li>
                ))}
              </ul>
              {current ? (
                <div className="flex items-center justify-center gap-1.5 text-[12px] text-brand font-medium py-2 rounded-lg bg-brand/10 border border-brand/20">
                  <CheckCircle2 size={13} /> Current plan
                </div>
              ) : plan === 'trial' ? (
                subscribed ? (
                  <button onClick={portal} disabled={busy === 'portal'}
                          className="w-full text-[12px] text-slate-400 border border-white/[0.1] py-2.5 rounded-lg hover:bg-white/[0.04] transition-colors">
                    Cancel subscription
                  </button>
                ) : <p className="text-[11px] text-slate-600 text-center py-2">14-day trial, no card required</p>
              ) : !stripeConfigured ? (
                <Link to="/support" className="block w-full text-center text-[12px] font-medium border border-brand/30 text-brand py-2.5 rounded-lg hover:bg-brand/10 transition-colors">
                  Contact us to {up ? 'upgrade' : 'change plan'}
                </Link>
              ) : (
                <button onClick={() => (subscribed ? portal() : checkout(plan))} disabled={busy === plan || busy === 'portal'}
                        className={`w-full text-[12px] font-medium py-2.5 rounded-lg disabled:opacity-40 transition-colors
                          ${up ? 'bg-brand text-white hover:bg-ember-dark' : 'border border-white/[0.12] text-slate-300 hover:bg-white/[0.04]'}`}>
                  {busy === plan ? 'Redirecting…' : `${up ? 'Upgrade' : 'Downgrade'} to ${p.label}`}
                </button>
              )}
            </div>
          )
        })}
      </div>

      <section className="glass-card border border-white/[0.07] rounded-xl p-5">
        <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100 mb-4">
          <FileText size={14} className="text-slate-500" /> Billing history
        </h2>
        {invoices === null ? (
          <p className="text-[12.5px] text-slate-600">Loading…</p>
        ) : invoices.length === 0 ? (
          <p className="text-[12.5px] text-slate-600">No invoices yet — they'll appear here after your first payment.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-left text-slate-500 border-b border-white/[0.06]">
                  <th className="font-medium py-2 pr-4">Date</th>
                  <th className="font-medium py-2 pr-4">Invoice</th>
                  <th className="font-medium py-2 pr-4">Amount</th>
                  <th className="font-medium py-2 pr-4">Status</th>
                  <th className="font-medium py-2" />
                </tr>
              </thead>
              <tbody>
                {invoices.map(inv => (
                  <tr key={inv.id} className="border-b border-white/[0.04] last:border-0">
                    <td className="py-2.5 pr-4 text-slate-300">{new Date(inv.created).toLocaleDateString()}</td>
                    <td className="py-2.5 pr-4 text-slate-400 font-mono">{inv.number || '—'}</td>
                    <td className="py-2.5 pr-4 text-slate-300">${inv.amount_usd.toFixed(2)} {inv.currency}</td>
                    <td className="py-2.5 pr-4 capitalize text-slate-400">{inv.status}</td>
                    <td className="py-2.5 text-right whitespace-nowrap">
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
