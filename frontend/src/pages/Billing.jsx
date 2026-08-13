import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CreditCard, ExternalLink, CheckCircle2, Camera, Users, Clock, Sparkles, Rocket, Crown } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useToast } from '../context/ToastContext'
import PageHeader from '../components/PageHeader'

const PLAN_ORDER = ['trial', 'starter', 'pro']
const PLAN_ICON = { trial: Sparkles, starter: Rocket, pro: Crown }
const PLAN_FEATURES = {
  trial:   ['Full detection pipeline', 'Live feed & incident review', 'Email alerts'],
  starter: ['Everything in Trial', 'SMS + call to authorities', 'Shift scheduling'],
  pro:     ['Everything in Starter', 'Priority detection processing', 'Dedicated support'],
}

export default function Billing() {
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [status,  setStatus]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [busyPlan, setBusyPlan] = useState(null)

  const load = () => apiFetch('/billing/status').then(r => r.ok ? r.json() : null).then(setStatus).catch(() => {})
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

  const handleUpgrade = async (plan) => {
    setBusyPlan(plan)
    try {
      const { url } = await apiJson('/billing/checkout-session', { method: 'POST', body: JSON.stringify({ plan }) })
      window.location.href = url
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not start checkout' })
      setBusyPlan(null)
    }
  }

  const handleManage = async () => {
    setLoading(true)
    try {
      const { url } = await apiJson('/billing/portal-session', { method: 'POST' })
      window.location.href = url
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not open billing portal' })
    } finally {
      setLoading(false)
    }
  }

  if (!status) return <div className="max-w-6xl fade-up"><PageHeader title="Billing" subtitle="Plan, usage & payment" /></div>

  const { org, usage, limits, plans, stripe_configured: stripeConfigured } = status
  const trialDaysLeft = org.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(org.trial_ends_at) - Date.now()) / 86400_000))
    : null

  return (
    <div className="max-w-6xl space-y-6 fade-up">
      <PageHeader title="Billing" subtitle="Plan, usage & payment">
        {org.stripe_customer_id && (
          <button onClick={handleManage} disabled={loading}
                  className="flex items-center gap-1.5 text-[12px] font-medium text-brand border border-brand/30 rounded-lg px-3 py-2 hover:bg-brand/10 transition-colors disabled:opacity-40">
            <CreditCard size={13} /> Manage billing <ExternalLink size={11} />
          </button>
        )}
      </PageHeader>

      {/* ── Stat strip ─────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Current Plan" value={limits.label}
                  badge={org.subscription_status} />
        <StatCard label="Cameras Used" value={`${usage.cameras}/${limits.max_cameras}`} icon={Camera}
                  danger={usage.cameras >= limits.max_cameras} />
        <StatCard label="Users Used" value={`${usage.users}/${limits.max_users}`} icon={Users}
                  danger={usage.users >= limits.max_users} />
        <StatCard label={org.plan === 'trial' ? 'Trial Ends In' : 'Renews'} icon={Clock}
                  value={org.plan === 'trial'
                    ? (trialDaysLeft > 0 ? `${trialDaysLeft}d` : 'Ended')
                    : (org.current_period_end ? new Date(org.current_period_end).toLocaleDateString() : '—')} />
      </div>

      {/* ── Plan cards ─────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {PLAN_ORDER.map(plan => {
          const isCurrent = org.plan === plan
          const isTrial = plan === 'trial'
          const Icon = PLAN_ICON[plan]
          const cameras = isTrial ? limits.max_cameras : plans[plan]?.max_cameras
          const users   = isTrial ? limits.max_users   : plans[plan]?.max_users
          return (
            <div key={plan} className={`glass-card rounded-xl p-5 border flex flex-col gap-4 relative
              ${isCurrent ? 'border-brand/40' : plan === 'starter' ? 'border-white/[0.12]' : 'border-white/[0.07]'}`}>
              {plan === 'starter' && !isCurrent && (
                <span className="absolute -top-2.5 left-5 text-[9px] font-raj font-bold tracking-widest uppercase bg-brand text-void px-2 py-0.5 rounded-full">
                  Popular
                </span>
              )}
              <div className="flex items-center gap-2.5">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0
                  ${isCurrent ? 'bg-brand/15 text-brand' : 'bg-white/[0.04] text-slate-500'}`}>
                  <Icon size={16} />
                </div>
                <div>
                  <p className="font-raj font-semibold text-[15px] text-white capitalize">{plan}</p>
                  <p className="font-raj font-bold text-[22px] text-white leading-none mt-0.5">
                    {isTrial ? 'Free' : `$${plans[plan].amount_usd}`}
                    {!isTrial && <span className="text-[11px] text-slate-600 font-normal">/mo</span>}
                  </p>
                </div>
              </div>

              <div className="text-[11px] text-slate-500 flex items-center gap-3 pb-3 border-b border-white/[0.06]">
                <span>{cameras} cameras</span>
                <span className="w-1 h-1 rounded-full bg-slate-700" />
                <span>{users} users</span>
              </div>

              <ul className="space-y-2 text-[12px] text-slate-400 flex-1">
                {PLAN_FEATURES[plan].map(f => (
                  <li key={f} className="flex items-start gap-2">
                    <CheckCircle2 size={13} className="text-brand shrink-0 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>

              {isCurrent ? (
                <div className="flex items-center justify-center gap-1.5 text-[12px] text-brand font-medium py-2 rounded-lg bg-brand/10 border border-brand/20">
                  <CheckCircle2 size={13} /> Current plan
                </div>
              ) : !isTrial ? (
                // Until card payment is live, offer the route that actually
                // works (we change the plan by hand) rather than a dead button
                // whose only explanation was a developer-facing notice.
                stripeConfigured ? (
                  <button onClick={() => handleUpgrade(plan)} disabled={busyPlan === plan}
                          className="w-full text-[12px] font-medium bg-brand text-void py-2.5 rounded-lg hover:bg-brand/85 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                    {busyPlan === plan ? 'Redirecting…' : `Upgrade to ${plan}`}
                  </button>
                ) : (
                  <Link to="/support"
                        className="block w-full text-center text-[12px] font-medium border border-brand/30 text-brand py-2.5 rounded-lg hover:bg-brand/10 transition-colors">
                    Contact us to upgrade
                  </Link>
                )
              ) : (
                <p className="text-[11px] text-slate-700 text-center py-2">14-day trial, no card required</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StatCard({ label, value, icon: Icon, badge, danger }) {
  return (
    <div className="glass-card rounded-xl p-4 border border-white/[0.07]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        {Icon && <Icon size={14} className={danger ? 'text-hazard' : 'text-slate-500'} />}
      </div>
      <p className={`font-raj font-bold text-[20px] leading-none capitalize ${danger ? 'text-hazard' : 'text-white'}`}>
        {value}
      </p>
      {badge && (
        <span className={`inline-block mt-2 text-[10px] font-semibold px-2 py-0.5 rounded-md capitalize
          ${badge === 'active' ? 'bg-safe/15 text-safe'
            : badge === 'trialing' ? 'bg-brand/15 text-brand'
            : 'bg-hazard/15 text-hazard'}`}>
          {badge}
        </span>
      )}
    </div>
  )
}
