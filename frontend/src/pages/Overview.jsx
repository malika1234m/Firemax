import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Home, KeyRound, CreditCard, UserCog, BookOpen, ArrowRight, CheckCircle2, AlertCircle,
  Clock, Activity, Wallet, PlugZap, Rocket,
} from 'lucide-react'
import { apiFetch } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useOrganization } from '../context/OrganizationContext'
import { useConnection } from '../hooks/useConnection'
import { STATUS_STYLE, timeAgo } from '../lib/homeAssistant'

/**
 * The account at a glance. Deliberately nothing about cameras or detections:
 * those live in the customer's Home Assistant. This page answers "is my
 * account in order, and is my Home Assistant connected to it?"
 */

const EVENT_ICON = {
  token_generated: KeyRound, token_revoked: KeyRound,
  ha_connected: PlugZap, ha_removed: PlugZap,
  subscription_changed: Wallet, payment_completed: CreditCard,
  setup_completed: CheckCircle2,
}

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

function Card({ title, icon: Icon, action, children }) {
  return (
    <section className="glass-card border border-white/[0.07] rounded-xl p-5 flex flex-col">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100">
          <Icon size={14} className="text-slate-500" /> {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2 border-b border-white/[0.04] last:border-0">
      <span className="text-[12.5px] text-slate-500">{label}</span>
      <span className="text-[12.5px] text-slate-200 text-right">{children}</span>
    </div>
  )
}

export default function Overview() {
  const { user, isAdmin } = useAuth()
  const { org } = useOrganization()
  const { licence, status, allowed } = useConnection()
  const [billing, setBilling] = useState(null)
  const [events, setEvents] = useState(null)

  useEffect(() => {
    apiFetch('/billing/status').then(r => (r.ok ? r.json() : null)).then(setBilling).catch(() => {})
    apiFetch('/organizations/me/activity').then(r => (r.ok ? r.json() : [])).then(setEvents).catch(() => setEvents([]))
  }, [])

  const setupUnfinished = isAdmin && org && !org.onboarding_completed
  const firstName = user?.name?.split(' ')[0] ?? ''

  const summary =
    status.state === 'connected' ? 'Everything is in order — your Home Assistant is connected to FiremeX.'
    : status.state === 'quiet' ? 'Your Home Assistant has not checked in recently. See the connection card below.'
    : status.state === 'never' ? 'Your account is ready. Connect your Home Assistant to finish setting up.'
    : 'Here is the state of your FiremeX account.'

  const sub = billing?.subscription
  const day = (d) => new Date(d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
  const nextBilling = !sub ? '—'
    : sub.state === 'trial' ? `Trial ends in ${sub.trial_days_left} day${sub.trial_days_left === 1 ? '' : 's'}`
    : sub.cancel_at_period_end ? `Ends ${day(sub.renews_at)}`
    : billing.has_subscription && sub.renews_at ? day(sub.renews_at)
    : sub.plan_source === 'manual' ? 'Managed by FiremeX' : '—'
  const STATE_TEXT = { trial: 'Free trial', active: 'Active', grace: 'Payment failed — retrying', free: sub?.trial_ended ? 'Trial ended' : 'Free' }

  return (
    <div className="max-w-6xl space-y-6 fade-up">
      {/* ── Welcome ── */}
      <div>
        <h1 className="font-raj font-bold text-[24px] text-white">{greeting()}{firstName && `, ${firstName}`}</h1>
        <p className="text-slate-400 text-[14px] mt-1">{summary}</p>
      </div>

      {setupUnfinished && (
        <div className="glass-card border border-brand/30 bg-brand/[0.05] rounded-xl p-4 flex flex-wrap items-center gap-3">
          <Rocket size={18} className="text-brand shrink-0" />
          <p className="text-[13px] text-slate-300 flex-1 min-w-[200px]">
            Your setup is not finished yet. Pick up where you left off.
          </p>
          <Link to="/welcome" className="inline-flex items-center gap-1.5 bg-brand text-white text-[12.5px] font-semibold px-4 py-2 rounded-lg hover:bg-ember-dark transition-colors">
            Resume setup <ArrowRight size={13} />
          </Link>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-5">
        {/* ── Home Assistant connection ── */}
        <Card title="Home Assistant Connection" icon={Home}
              action={<Link to="/home-assistant" className="text-[12px] text-brand hover:underline">Details</Link>}>
          {!allowed ? (
            <p className="text-[12.5px] text-slate-500">Ask an admin of your account for the connection details.</p>
          ) : (
            <>
              <span className={`self-start inline-flex items-center gap-1.5 text-[12px] font-medium px-2.5 py-1 rounded-lg border mb-3 ${STATUS_STYLE[status.state]}`}>
                {status.state === 'connected' ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
                {status.label ?? 'Checking…'}
              </span>
              <Row label="Last successful communication">
                {status.lastSeen ? `${timeAgo(status.lastSeen)}` : 'Never'}
              </Row>
              <Row label="Add-on version">{status.version || '—'}</Row>
              <Row label="Home Assistant">
                {status.count ?? 0} of {licence?.max_installs ?? '—'} connected
              </Row>
              <Row label="Access token">
                {!licence ? '—' : licence.entitled
                  ? <span className="text-safe">Active — up to {licence.max_cameras} cameras</span>
                  : <span className="text-warn">Free plan — 1 camera</span>}
              </Row>
              {status.state !== 'connected' && status.state !== 'loading' && (
                <Link to="/home-assistant#reconnect" className="mt-3 text-[12px] text-brand hover:underline self-start">
                  {status.state === 'never' ? 'How to connect' : 'How to reconnect'} →
                </Link>
              )}
            </>
          )}
        </Card>

        {/* ── Subscription ── */}
        <Card title="Subscription" icon={Wallet}
              action={<Link to="/billing" className="text-[12px] text-brand hover:underline">Plans & Billing</Link>}>
          <Row label="Current plan">{sub?.label ?? '—'}</Row>
          <Row label="Status">
            <span className={sub?.state === 'grace' || sub?.trial_ended ? 'text-hazard' : ''}>{sub ? STATE_TEXT[sub.state] : '—'}</span>
          </Row>
          <Row label="Cameras">{sub ? `Up to ${sub.cameras}` : '—'}</Row>
          <Row label="Billing">{!sub ? '—' : sub.interval === 'year' ? 'Yearly' : sub.interval === 'month' ? 'Monthly' : sub.state === 'trial' ? 'Free trial' : '—'}</Row>
          <Row label="Next billing date">{nextBilling}</Row>
          <Row label="Team members">
            {billing ? `${billing.usage.users} of ${billing.limits.max_users}` : '—'}
          </Row>
        </Card>
      </div>

      {/* ── Quick actions ── */}
      <section>
        <h2 className="text-[14.5px] font-semibold text-slate-100 mb-3">Quick actions</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { to: '/tokens', icon: KeyRound, label: 'Access token', text: 'Copy or generate a token', admin: true },
            { to: '/home-assistant', icon: BookOpen, label: 'Setup guide', text: 'Install in Home Assistant' },
            { to: '/billing', icon: CreditCard, label: 'Subscription', text: 'Change plan, invoices', admin: true },
            { to: '/settings', icon: UserCog, label: 'Account', text: 'Profile, password, team' },
          ].filter(a => !a.admin || isAdmin).map(({ to, icon: Icon, label, text }) => (
            <Link key={to} to={to}
                  className="glass-card border border-white/[0.07] rounded-xl p-4 hover:border-brand/30 transition-colors group">
              <Icon size={17} className="text-brand" />
              <p className="text-[13px] text-slate-200 font-medium mt-3">{label}</p>
              <p className="text-[11.5px] text-slate-500 mt-0.5">{text}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* ── Recent account activity ── */}
      <Card title="Recent account activity" icon={Activity}>
        {events === null ? (
          <p className="text-[12.5px] text-slate-600">Loading…</p>
        ) : events.length === 0 ? (
          <p className="text-[12.5px] text-slate-600">Nothing yet. Token, connection and payment events will appear here.</p>
        ) : (
          <ul className="divide-y divide-white/[0.04]">
            {events.map((e, i) => {
              const Icon = EVENT_ICON[e.kind] ?? Clock
              return (
                <li key={i} className="flex items-center gap-3 py-2.5">
                  <span className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center shrink-0">
                    <Icon size={13} className="text-slate-400" />
                  </span>
                  <span className="text-[12.5px] text-slate-300 flex-1 min-w-0">{e.message}</span>
                  <span className="text-[11.5px] text-slate-600 shrink-0" title={new Date(e.at).toLocaleString()}>
                    {timeAgo(e.at)}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}
