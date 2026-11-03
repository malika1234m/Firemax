import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, Check, CheckCircle2, Home, KeyRound, Loader2, PartyPopper,
  RefreshCw, Sparkles, Wallet, Radio,
} from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useOrganization } from '../context/OrganizationContext'
import { useToast } from '../context/ToastContext'
import { useConnection } from '../hooks/useConnection'
import { Snippet } from '../components/Copy'
import InstallSteps from '../components/InstallSteps'
import { timeAgo } from '../lib/homeAssistant'
import logo from '../assets/logo.png'

/**
 * First-time setup: plan → access token → install in Home Assistant → verify.
 *
 * Every step is saved on the server as it is reached, so an admin who leaves
 * half-way (to find their Home Assistant password, say) comes back to the same
 * step, on any computer. The website's whole job here is the account and the
 * token; the fire detection itself is set up inside Home Assistant.
 */
const STEPS = [
  { id: 'welcome', label: 'Welcome',        icon: Sparkles },
  { id: 'plan',    label: 'Plan',           icon: Wallet },
  { id: 'token',   label: 'Access token',   icon: KeyRound },
  { id: 'install', label: 'Home Assistant', icon: Home },
  { id: 'verify',  label: 'Verify',         icon: Radio },
  { id: 'done',    label: 'Finish',         icon: PartyPopper },
]

function Progress({ index }) {
  return (
    <ol className="flex items-center gap-1.5 overflow-x-auto pb-1">
      {STEPS.map((s, i) => (
        <li key={s.id} className="flex items-center gap-1.5 shrink-0">
          <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium border
            ${i < index ? 'border-safe/25 bg-safe/[0.07] text-safe'
              : i === index ? 'border-brand/40 bg-brand/[0.12] text-brand'
              : 'border-white/[0.07] text-slate-600'}`}>
            {i < index ? <Check size={11} strokeWidth={3} /> : <span className="font-mono">{i + 1}</span>}
            {s.label}
          </span>
          {i < STEPS.length - 1 && <span className="w-3 h-px bg-white/[0.1]" />}
        </li>
      ))}
    </ol>
  )
}

export default function Onboarding() {
  const { user } = useAuth()
  const { org, setOrg } = useOrganization()
  const { toast } = useToast()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const saved = STEPS.findIndex(s => s.id === org?.onboarding_step)
  const [index, setIndex] = useState(saved > 0 ? saved : 0)

  const save = async (step, completed = false) => {
    try {
      setOrg(await apiJson('/organizations/me/onboarding', {
        method: 'PUT', body: JSON.stringify({ step, completed }),
      }))
    } catch { /* progress is a convenience; never block setup on it */ }
  }

  const go = (i) => {
    setIndex(i)
    save(STEPS[i].id, STEPS[i].id === 'done')
  }

  // Back from Stripe checkout, started on the plan step.
  useEffect(() => {
    const checkout = params.get('checkout')
    if (!checkout) return
    if (checkout === 'success') {
      toast({ type: 'success', message: 'Subscription active — thank you!' })
      go(STEPS.findIndex(s => s.id === 'token'))
    }
    setParams({}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Mark the setup as started the moment it is first opened, so the admin is
  // not sent back here on every sign-in — the Overview offers to resume it.
  useEffect(() => {
    if (org && !org.onboarding_step) save('welcome')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [org?.org_id])

  const later = async () => {
    await save(STEPS[index].id)
    navigate('/')
  }

  const step = STEPS[index].id
  const firstName = user?.name?.split(' ')[0] ?? 'there'

  return (
    <div className="min-h-screen bg-void bg-dot-grid">
      <header className="max-w-3xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <img src={logo} alt="" className="w-8 h-8 rounded-lg" />
          <span className="font-raj font-bold text-[17px] text-white">Fireme<span className="text-brand">X</span></span>
        </div>
        {step !== 'done' && (
          <button onClick={later} className="text-[12px] text-slate-500 hover:text-slate-300 transition-colors">
            Finish later
          </button>
        )}
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 pb-16">
        <Progress index={index} />

        <div className="glass-card border border-white/[0.08] rounded-2xl p-5 sm:p-8 mt-5 fade-up" key={step}>
          {step === 'welcome' && <Welcome name={firstName} onNext={() => go(1)} />}
          {step === 'plan' && <PlanStep org={org} onNext={() => go(2)} />}
          {step === 'token' && <TokenStep />}
          {step === 'install' && <InstallStep />}
          {step === 'verify' && <VerifyStep onNext={() => go(5)} />}
          {step === 'done' && <DoneStep />}

          {!['welcome', 'plan', 'verify', 'done'].includes(step) && (
            <div className="flex items-center justify-between mt-8 pt-5 border-t border-white/[0.06]">
              <BackButton onClick={() => go(index - 1)} />
              <button onClick={() => go(index + 1)}
                      className="inline-flex items-center gap-2 bg-brand text-white text-[13px] font-semibold px-5 py-2.5 rounded-lg hover:bg-ember-dark transition-colors">
                {step === 'install' ? "I've pressed Start" : 'Continue'} <ArrowRight size={14} />
              </button>
            </div>
          )}
          {['plan', 'verify'].includes(step) && (
            <div className="mt-8 pt-5 border-t border-white/[0.06]">
              <BackButton onClick={() => go(index - 1)} />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function BackButton({ onClick }) {
  return (
    <button onClick={onClick} className="inline-flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-slate-300 transition-colors">
      <ArrowLeft size={13} /> Back
    </button>
  )
}

function Title({ children, sub }) {
  return (
    <div className="mb-6">
      <h1 className="font-raj font-bold text-[24px] sm:text-[28px] text-white leading-tight">{children}</h1>
      {sub && <p className="text-[13.5px] text-slate-400 mt-2 leading-relaxed">{sub}</p>}
    </div>
  )
}

function Welcome({ name, onNext }) {
  return (
    <>
      <Title sub="Setting up takes about five minutes. You can stop at any point and pick up where you left off.">
        Welcome to FiremeX, {name}
      </Title>
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="rounded-xl border border-white/[0.07] bg-black/20 p-4">
          <p className="text-[12px] font-semibold text-brand uppercase tracking-wider">This website</p>
          <p className="text-[13px] text-slate-300 mt-2 leading-relaxed">
            Your account, subscription and access token — and a check that your Home Assistant is connected.
          </p>
        </div>
        <div className="rounded-xl border border-white/[0.07] bg-black/20 p-4">
          <p className="text-[12px] font-semibold text-live uppercase tracking-wider">Your Home Assistant</p>
          <p className="text-[13px] text-slate-300 mt-2 leading-relaxed">
            Your cameras, the fire detection and the alerts. Video never leaves your building.
          </p>
        </div>
      </div>
      <button onClick={onNext}
              className="mt-8 inline-flex items-center gap-2 bg-brand text-white text-[13px] font-semibold px-5 py-2.5 rounded-lg hover:bg-ember-dark transition-colors">
        Let's get started <ArrowRight size={14} />
      </button>
    </>
  )
}

function PlanStep({ org, onNext }) {
  const { toast } = useToast()
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(null)
  useEffect(() => {
    apiFetch('/billing/status').then(r => (r.ok ? r.json() : null)).then(setStatus).catch(() => {})
  }, [])

  const upgrade = async (plan) => {
    setBusy(plan)
    try {
      const { url } = await apiJson('/billing/checkout-session', {
        method: 'POST', body: JSON.stringify({ plan, return_to: 'welcome' }),
      })
      window.location.href = url
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not start checkout' })
      setBusy(null)
    }
  }

  if (!status) return <Loader2 size={18} className="animate-spin text-slate-500" />
  const trialDays = org?.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(org.trial_ends_at) - Date.now()) / 86400_000)) : null
  const plans = Object.entries(status.plans)

  return (
    <>
      <Title sub={org?.plan === 'trial' && trialDays !== null
        ? `You are on the free trial, with ${trialDays} day${trialDays === 1 ? '' : 's'} left. You can keep it and choose a plan later.`
        : 'Confirm your plan. You can change it at any time under Plans & Billing.'}>
        Choose your plan
      </Title>
      <div className="grid sm:grid-cols-3 gap-3">
        {plans.map(([id, p]) => {
          const current = org?.plan === id
          return (
            <div key={id} className={`rounded-xl border p-4 flex flex-col ${current ? 'border-brand/45 bg-brand/[0.05]' : 'border-white/[0.07]'}`}>
              <p className="font-raj font-semibold text-[15px] text-white">{p.label}</p>
              <p className="font-raj font-bold text-[22px] text-white leading-none mt-1">
                {p.amount_usd ? `$${p.amount_usd}` : 'Free'}
                {p.amount_usd ? <span className="text-[11px] text-slate-600 font-normal">/month</span> : null}
              </p>
              <p className="text-[11.5px] text-slate-500 mt-2">
                {p.max_installs} Home Assistant installation{p.max_installs === 1 ? '' : 's'} · unlimited cameras
              </p>
              <div className="flex-1" />
              {current ? (
                <button onClick={onNext}
                        className="mt-4 w-full inline-flex items-center justify-center gap-1.5 bg-brand text-white text-[12.5px] font-semibold py-2 rounded-lg hover:bg-ember-dark transition-colors">
                  Continue with {p.label} <ArrowRight size={13} />
                </button>
              ) : p.purchasable && status.stripe_configured ? (
                <button onClick={() => upgrade(id)} disabled={busy === id}
                        className="mt-4 w-full text-[12.5px] font-medium border border-brand/35 text-brand py-2 rounded-lg hover:bg-brand/10 disabled:opacity-50 transition-colors">
                  {busy === id ? 'Opening checkout…' : `Choose ${p.label}`}
                </button>
              ) : p.purchasable ? (
                <Link to="/support" className="mt-4 block text-center text-[12.5px] font-medium border border-white/[0.1] text-slate-400 py-2 rounded-lg hover:bg-white/[0.04] transition-colors">
                  Contact us
                </Link>
              ) : null}
            </div>
          )
        })}
      </div>
    </>
  )
}

function TokenStep() {
  const { licence, allowed } = useConnection()
  return (
    <>
      <Title sub="Home Assistant uses this token to prove your FiremeX subscription. Without it the add-on still works, but watches only one camera.">
        Your access token
      </Title>
      {allowed
        ? <Snippet label="Access token" code={licence?.licence_key || 'Loading…'} />
        : <p className="text-[13px] text-slate-400">Only an admin can see the access token.</p>}
      <p className="text-[12px] text-slate-500 mt-4 leading-relaxed">
        Treat it like a password. You can copy it again, or replace it, under{' '}
        <span className="text-slate-300">Access Tokens</span> at any time.
      </p>
    </>
  )
}

function InstallStep() {
  const { licence } = useConnection()
  return (
    <>
      <Title sub="Do this in Home Assistant, then come back to this page. Requires Home Assistant OS or Supervised.">
        Install FiremeX in Home Assistant
      </Title>
      <InstallSteps token={licence?.licence_key ?? ''} />
    </>
  )
}

function VerifyStep({ onNext }) {
  // Re-checks every 5 seconds: the customer is usually still in Home Assistant
  // pressing Start, and the step should turn green by itself when it checks in.
  const { status, checking, reload } = useConnection({ pollMs: 5000 })
  const connected = status.state === 'connected'
  return (
    <>
      <Title sub="FiremeX checks your access token with us when the add-on starts. As soon as it does, this page turns green.">
        Verify the connection
      </Title>

      <div className={`rounded-xl border p-5 flex items-center gap-4
        ${connected ? 'border-safe/30 bg-safe/[0.06]' : 'border-white/[0.08] bg-black/20'}`}>
        {connected
          ? <CheckCircle2 size={26} className="text-safe shrink-0" />
          : <Loader2 size={24} className="text-slate-500 animate-spin shrink-0" />}
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-medium text-slate-200">
            {connected ? 'Home Assistant is connected' : 'Waiting for Home Assistant…'}
          </p>
          <p className="text-[12px] text-slate-500 mt-0.5">
            {connected
              ? `Add-on ${status.version || ''} checked in ${timeAgo(status.lastSeen)}.`
              : 'Checking every few seconds.'}
          </p>
        </div>
        <button onClick={reload} disabled={checking}
                className="inline-flex items-center gap-1.5 text-[12px] text-slate-400 hover:text-slate-200 border border-white/[0.1] rounded-lg px-3 py-1.5 disabled:opacity-40 transition-colors shrink-0">
          <RefreshCw size={12} className={checking ? 'animate-spin' : ''} /> Check now
        </button>
      </div>

      {!connected && (
        <div className="mt-5 text-[12.5px] text-slate-500 space-y-1.5">
          <p className="text-slate-400 font-medium">Not turning green after a minute?</p>
          <p>• Check the token is pasted into <span className="font-mono text-slate-400">licence_key</span> and you pressed Save, then restart the add-on.</p>
          <p>• Open the add-on's <span className="text-slate-300">Log</span> tab — it says what happened with the licence.</p>
          <p>• Home Assistant needs internet once for this check.</p>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mt-8">
        <button onClick={onNext}
                className={`inline-flex items-center gap-2 text-[13px] font-semibold px-5 py-2.5 rounded-lg transition-colors
                  ${connected ? 'bg-brand text-white hover:bg-ember-dark' : 'border border-white/[0.12] text-slate-300 hover:bg-white/[0.04]'}`}>
          {connected ? 'Continue' : 'Skip for now'} <ArrowRight size={14} />
        </button>
      </div>
    </>
  )
}

function DoneStep() {
  return (
    <div className="text-center py-4">
      <div className="w-14 h-14 rounded-2xl bg-safe/10 border border-safe/25 flex items-center justify-center mx-auto">
        <CheckCircle2 size={26} className="text-safe" />
      </div>
      <h1 className="font-raj font-bold text-[26px] text-white mt-5">You're all set</h1>
      <p className="text-[13.5px] text-slate-400 mt-2 max-w-md mx-auto leading-relaxed">
        FiremeX now watches your cameras inside Home Assistant. Open the <span className="text-slate-200">FiremeX</span>{' '}
        dashboard in the Home Assistant sidebar to see them. This website keeps your account, token and subscription.
      </p>
      <Link to="/"
            className="mt-7 inline-flex items-center gap-2 bg-brand text-white text-[13px] font-semibold px-5 py-2.5 rounded-lg hover:bg-ember-dark transition-colors">
        Go to my account <ArrowRight size={14} />
      </Link>
    </div>
  )
}
