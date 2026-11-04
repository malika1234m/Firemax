import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, Check, Clock, Cpu, CreditCard, Home, KeyRound, LifeBuoy, Loader2,
  Lock, PlugZap, RefreshCw, ScrollText, ShieldCheck, Users, Video, Wifi, BellRing, Flame,
} from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useOrganization } from '../context/OrganizationContext'
import { useToast } from '../context/ToastContext'
import { useConnection } from '../hooks/useConnection'
import { CopyButton } from '../components/Copy'
import InstallSteps from '../components/InstallSteps'
import PlanPicker, { IntervalToggle } from '../components/PlanPicker'
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
  { id: 'welcome', label: 'Welcome',        hint: 'What goes where' },
  { id: 'plan',    label: 'Plan',           hint: 'Keep the trial or pick one' },
  { id: 'token',   label: 'Access token',   hint: 'The key for your add-on' },
  { id: 'install', label: 'Home Assistant', hint: 'Install the add-on' },
  { id: 'verify',  label: 'Verify',         hint: 'Wait for it to check in' },
  { id: 'done',    label: 'Finish',         hint: 'You are running' },
]

/** Vertical timeline in the side rail. Finished steps can be revisited. */
function Rail({ index, onPick }) {
  return (
    <ol className="relative">
      {STEPS.map((s, i) => {
        const done = i < index
        const current = i === index
        return (
          <li key={s.id} className="relative pb-6 last:pb-0">
            {i < STEPS.length - 1 && (
              <span aria-hidden className={`absolute left-[13px] top-8 bottom-1 w-px
                ${done ? 'bg-safe/40' : 'bg-white/[0.08]'}`} />
            )}
            <button type="button" onClick={() => done && onPick(i)} disabled={!done}
                    aria-current={current ? 'step' : undefined}
                    className="group flex items-start gap-3.5 text-left w-full rounded-md disabled:cursor-default
                               focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60">
              <span className={`relative w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-[11px] font-mono font-bold transition-colors
                ${done ? 'bg-safe/15 text-safe border border-safe/30'
                  : current ? 'bg-brand text-white shadow-[0_0_0_4px_rgba(194,65,12,0.18)]'
                  : 'border border-white/[0.12] text-slate-500'}`}>
                {done ? <Check size={13} strokeWidth={3} /> : i + 1}
              </span>
              <span className="pt-0.5">
                <span className={`block text-[13.5px] font-medium leading-tight
                  ${current ? 'text-white' : done ? 'text-slate-300 group-hover:text-white' : 'text-slate-500'}`}>
                  {s.label}
                </span>
                <span className={`block text-[12px] mt-1 ${current ? 'text-slate-300' : 'text-slate-500'}`}>{s.hint}</span>
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <img src={logo} alt="" className="w-8 h-8 rounded-lg" />
      <span className="font-raj font-bold text-[18px] text-white tracking-wide">Fireme<span className="text-brand">X</span></span>
    </div>
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
    window.scrollTo({ top: 0 })
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

  // Move focus to the new step so keyboard and screen-reader users land on
  // its heading instead of the button they just pressed, which is now gone.
  const stepRef = useRef(null)
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return }
    stepRef.current?.focus({ preventScroll: true })
  }, [index])

  const step = STEPS[index].id
  const firstName = user?.name?.split(' ')[0] ?? 'there'
  const next = () => go(index + 1)
  const back = index > 0 && step !== 'done' ? () => go(index - 1) : null

  return (
    <div className="min-h-dvh bg-void lg:grid lg:grid-cols-[340px_minmax(0,1fr)]">
      {/* ── Side rail (desktop) ── */}
      <aside className="hidden lg:flex flex-col h-dvh sticky top-0 border-r border-white/[0.06] bg-panel overflow-hidden">
        <div aria-hidden className="absolute inset-0 ember-glow pointer-events-none" />
        <div className="relative flex flex-col h-full px-8 py-8">
          <Brand />
          <div className="mt-12">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-brand">Account setup</p>
            <p className="font-raj font-bold text-[26px] leading-[1.1] text-white mt-2">
              Get FiremeX watching your cameras
            </p>
            <p className="flex items-center gap-1.5 text-[12.5px] text-slate-400 mt-3">
              <Clock size={13} /> About five minutes. Progress is saved.
            </p>
          </div>
          <div className="mt-10">
            <Rail index={step === 'done' ? STEPS.length : index} onPick={go} />
          </div>
          <div className="mt-auto pt-8 space-y-4">
            <Link to="/support"
                  className="flex items-start gap-3 rounded-lg border border-white/[0.07] bg-white/[0.02] p-3.5 hover:border-white/[0.14] transition-colors">
              <LifeBuoy size={16} className="text-slate-400 mt-0.5 shrink-0" />
              <span>
                <span className="block text-[12.5px] text-slate-300 font-medium">Stuck on a step?</span>
                <span className="block text-[12px] text-slate-400 mt-0.5">Guides, answers and a way to reach us.</span>
              </span>
            </Link>
            {step !== 'done' && (
              <button onClick={later} className="btn-ghost">Finish later — take me to my account</button>
            )}
          </div>
        </div>
      </aside>

      {/* ── Content ── */}
      <div className="min-h-dvh flex flex-col bg-dot-grid">
        <header className="lg:hidden sticky top-0 z-10 bg-void/90 backdrop-blur border-b border-white/[0.06]">
          <div className="px-4 sm:px-6 h-14 flex items-center justify-between">
            <Brand />
            {step !== 'done' && <button onClick={later} className="btn-ghost">Finish later</button>}
          </div>
          <div className="h-0.5 bg-white/[0.06]" role="progressbar" aria-label="Setup progress"
               aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={index + 1}>
            <div className="h-full bg-brand transition-[width] duration-500"
                 style={{ width: `${((index + 1) / STEPS.length) * 100}%` }} />
          </div>
        </header>

        <main className="flex-1 px-4 sm:px-8 lg:px-12 py-10 lg:py-20">
          <div ref={stepRef} tabIndex={-1} className="max-w-2xl mx-auto fade-up outline-none" key={step}>
            {step !== 'done' && (
              <p className="text-[12px] font-mono text-slate-400 mb-4">
                Step {index + 1} <span className="text-slate-700">/</span> {STEPS.length}
                <span className="lg:hidden text-slate-400"> · {STEPS[index].label}</span>
              </p>
            )}

            {step === 'welcome' && <Welcome name={firstName} onNext={next} />}
            {step === 'plan' && <PlanStep org={org} onNext={next} />}
            {step === 'token' && <TokenStep />}
            {step === 'install' && <InstallStep />}
            {step === 'verify' && <VerifyStep onNext={next} />}
            {step === 'done' && <DoneStep />}

            {['token', 'install'].includes(step) && (
              <Footer back={back}>
                <button onClick={next} className="btn-primary">
                  {step === 'install' ? "I've pressed Start" : 'Continue'} <ArrowRight size={15} />
                </button>
              </Footer>
            )}
            {step === 'plan' && <Footer back={back} />}
          </div>
        </main>
      </div>
    </div>
  )
}

function Footer({ back, children }) {
  return (
    <div className="flex items-center justify-between gap-4 mt-12 pt-6 border-t border-white/[0.06]">
      {back ? (
        <button onClick={back} className="btn-ghost"><ArrowLeft size={14} /> Back</button>
      ) : <span />}
      {children}
    </div>
  )
}

function Title({ children, sub }) {
  return (
    <div className="mb-8">
      <h1 className="font-raj font-bold text-[30px] sm:text-[38px] text-white leading-[1.05] tracking-tight">{children}</h1>
      {sub && <p className="text-[15px] text-slate-400 mt-4 leading-relaxed max-w-xl">{sub}</p>}
    </div>
  )
}

/* ── 1. Welcome ─────────────────────────────────────────────────────── */

function Side({ label, tone, items, note }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-panel/70 p-5">
      <p className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${tone}`}>{label}</p>
      <ul className="mt-4 space-y-3">
        {items.map(([Icon, text]) => (
          <li key={text} className="flex items-center gap-3 text-[13.5px] text-slate-300">
            <Icon size={15} className="text-slate-400 shrink-0" /> {text}
          </li>
        ))}
      </ul>
      {note && <p className="mt-4 pt-4 border-t border-white/[0.06] text-[12px] text-slate-400 flex items-center gap-2">{note}</p>}
    </div>
  )
}

function Welcome({ name, onNext }) {
  return (
    <>
      <Title sub="FiremeX lives in two places. Here's the split, so nothing later is a surprise.">
        Hi {name}, let's get you set up.
      </Title>

      <div className="grid sm:grid-cols-2 gap-4">
        <Side label="This website" tone="text-brand"
              items={[[CreditCard, 'Your plan and invoices'], [KeyRound, 'Your access token'], [PlugZap, 'Whether Home Assistant is connected']]} />
        <Side label="Your Home Assistant" tone="text-live"
              items={[[Video, 'Your cameras'], [Flame, 'Fire and smoke detection'], [BellRing, 'Alerts to your phone']]}
              note={<><Lock size={13} className="shrink-0" /> Video never leaves your building.</>} />
      </div>

      <div className="mt-8">
        <p className="text-[13px] font-medium text-slate-300">Before you start, have ready:</p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {[[Home, 'Home Assistant OS or Supervised'], [ShieldCheck, 'An admin login for it'], [Wifi, 'Internet on that machine, once']].map(([Icon, t]) => (
            <li key={t} className="inline-flex items-center gap-2 text-[12.5px] text-slate-400 rounded-full border border-white/[0.08] px-3 py-1.5">
              <Icon size={13} className="text-slate-400" /> {t}
            </li>
          ))}
        </ul>
      </div>

      <button onClick={onNext} className="btn-primary mt-10">
        Let's start <ArrowRight size={15} />
      </button>
    </>
  )
}

/* ── 2. Plan ────────────────────────────────────────────────────────── */

function PlanStep({ org, onNext }) {
  const { toast } = useToast()
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(null)
  const [interval, setPeriod] = useState('month')
  const [cameras, setCameras] = useState(5)
  useEffect(() => {
    apiFetch('/billing/status').then(r => (r.ok ? r.json() : null)).then(setStatus).catch(() => {})
  }, [])

  const upgrade = async (plan) => {
    setBusy(plan)
    try {
      const { url } = await apiJson('/billing/checkout-session', {
        method: 'POST', body: JSON.stringify({ plan, interval, cameras, return_to: 'welcome' }),
      })
      window.location.href = url
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not start checkout' })
      setBusy(null)
    }
  }

  const sub = status?.subscription
  const onTrial = sub?.state === 'trial'
  const actionFor = (p) => {
    if (p.plan_id === 'free') return onTrial ? { kind: 'none' } : sub?.state === 'free' ? { kind: 'current' } : { kind: 'none' }
    if (sub?.plan === p.plan_id && sub.state !== 'free') return { kind: 'current' }
    if (!status.stripe_configured) return { kind: 'secondary', label: 'Talk to us' }
    return { kind: 'secondary', label: `Choose ${p.label}` }
  }

  return (
    <>
      <Title sub={onTrial
        ? `Your free trial has ${sub.trial_days_left} day${sub.trial_days_left === 1 ? '' : 's'} left, with up to ${sub.cameras} cameras. Pick a plan now, or keep the trial and decide later.`
        : 'Plans are priced by camera. You can change or cancel at any time under Plans & Billing.'}>
        {onTrial ? 'Pick a plan, or keep the trial' : 'Pick a plan'}
      </Title>

      {!status ? (
        <div className="grid md:grid-cols-3 gap-4">
          {[0, 1, 2].map(i => <div key={i} className="h-72 rounded-xl border border-white/[0.06] bg-white/[0.02] animate-pulse" />)}
        </div>
      ) : (
        <>
          <div className="mb-5"><IntervalToggle interval={interval} onChange={setPeriod} /></div>
          <PlanPicker plans={status.plans} interval={interval} cameras={cameras} onCameras={setCameras}
                      actionFor={actionFor} busy={busy}
                      onChoose={(id) => (status.stripe_configured ? upgrade(id) : (window.location.href = '/support'))} />
          <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
            <p className="text-[12px] text-slate-400 flex items-center gap-2">
              <Lock size={12} /> Payments go through Stripe. FiremeX never sees your card number.
            </p>
            <button onClick={onNext} className="btn-primary">
              {onTrial ? 'Keep the trial for now' : 'Continue'} <ArrowRight size={15} />
            </button>
          </div>
        </>
      )}
    </>
  )
}

/* ── 3. Token ───────────────────────────────────────────────────────── */

function TokenStep() {
  const { licence, allowed } = useConnection()
  const key = licence?.licence_key
  return (
    <>
      <Title sub="Home Assistant shows this to us to prove you have a FiremeX plan. Without it the add-on still runs, but on one camera only.">
        This is your access token
      </Title>

      {!allowed ? (
        <p className="text-[14px] text-slate-400 rounded-xl border border-white/[0.07] bg-panel/70 p-5">
          Only an admin of your account can see the access token. Ask them to finish this step.
        </p>
      ) : (
        <div className="rounded-xl border border-white/[0.08] bg-panel overflow-hidden">
          <div className="flex items-center justify-between gap-3 px-5 py-3 border-b border-white/[0.06]">
            <span className="flex items-center gap-2 text-[12.5px] text-slate-400">
              <KeyRound size={14} className="text-brand" /> Access token
            </span>
            {key && <CopyButton text={key} label="Copy token" className="btn-secondary" />}
          </div>
          <div className="px-5 py-6">
            {key
              ? <code className="block font-mono text-[15px] sm:text-[17px] text-white break-all tracking-wide">{key}</code>
              : <div className="h-6 w-3/4 rounded bg-white/[0.05] animate-pulse" />}
          </div>
        </div>
      )}

      {/* What the field looks like on the other side, so it is easy to spot. */}
      <div className="mt-8">
        <p className="text-[13px] font-medium text-slate-300">You'll paste it here, in the add-on's Configuration tab:</p>
        <div className="mt-3 rounded-xl border border-dashed border-white/[0.1] p-4 max-w-md">
          <p className="text-[11px] text-slate-400 mb-1.5 font-mono">licence_key</p>
          <div className="h-10 rounded-md bg-white/[0.04] border border-white/[0.08] px-3 flex items-center font-mono text-[12.5px] text-slate-400">
            {key ? `${key.slice(0, 8)}…` : 'fmx_…'}
          </div>
        </div>
      </div>

      <p className="text-[12.5px] text-slate-400 mt-6 leading-relaxed max-w-xl">
        Keep it like a password. You can copy it again later, or swap it for a new one, under{' '}
        <span className="text-slate-300">Access Tokens</span>.
      </p>
    </>
  )
}

/* ── 4. Install ─────────────────────────────────────────────────────── */

function InstallStep() {
  const { licence } = useConnection()
  return (
    <>
      <Title sub="Keep this page open in one tab and Home Assistant in another. You'll only ever type the token.">
        Install FiremeX in Home Assistant
      </Title>
      <InstallSteps token={licence?.licence_key ?? ''} />
    </>
  )
}

/* ── 5. Verify ──────────────────────────────────────────────────────── */

function Node({ icon, label, sub, state }) {
  const ring = state === 'ok' ? 'border-safe/40 bg-safe/10 text-safe'
    : state === 'wait' ? 'border-white/[0.12] bg-white/[0.03] text-slate-400'
    : 'border-brand/40 bg-brand/10 text-brand'
  return (
    <div className="flex flex-col items-center text-center w-32 shrink-0">
      <div className="relative">
        {state === 'wait' && <span aria-hidden className="absolute inset-0 rounded-2xl border border-white/20 signal-ring" />}
        <div className={`relative w-14 h-14 rounded-2xl border flex items-center justify-center ${ring}`}>{icon}</div>
      </div>
      <p className="text-[12.5px] text-slate-200 font-medium mt-3">{label}</p>
      <p className="text-[11.5px] text-slate-400 mt-0.5">{sub}</p>
    </div>
  )
}

function VerifyStep({ onNext }) {
  // Re-checks every 5 seconds: the customer is usually still in Home Assistant
  // pressing Start, and the step should turn green by itself when it checks in.
  const { status, checking, reload } = useConnection({ pollMs: 5000 })
  const connected = status.state === 'connected'
  return (
    <>
      <Title sub={connected
        ? 'Your Home Assistant just checked in with your token. That was the last thing to do.'
        : 'When the add-on starts it checks your token with us. This page turns green on its own when that happens.'}>
        {connected ? 'Connected.' : 'Waiting for Home Assistant'}
      </Title>

      <div className={`rounded-2xl border px-6 py-8 transition-colors duration-500
        ${connected ? 'border-safe/30 bg-safe/[0.05]' : 'border-white/[0.08] bg-panel/70'}`}>
        <div className="flex items-start justify-center gap-2 sm:gap-4">
          <Node icon={<img src={logo} alt="" className="w-7 h-7 rounded-md" />} label="Your account" sub="FiremeX" state={connected ? 'ok' : 'brand'} />
          <div className="relative flex-1 max-w-[220px] mt-7">
            <div className={`h-px ${connected ? 'bg-safe/60' : 'border-t border-dashed border-white/[0.18]'}`} />
            {!connected && (
              <span aria-hidden className="signal-dot absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-brand shadow-[0_0_10px_rgba(194,65,12,0.9)]" />
            )}
            {connected && (
              <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-safe text-void flex items-center justify-center">
                <Check size={13} strokeWidth={3} />
              </span>
            )}
          </div>
          <Node icon={<Home size={24} />} label="Your Home Assistant"
                sub={connected ? `Add-on ${status.version || ''}`.trim() : 'Not heard from yet'}
                state={connected ? 'ok' : 'wait'} />
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-[12.5px]" aria-live="polite">
          {connected ? (
            <span className="text-safe">Checked in {timeAgo(status.lastSeen)}</span>
          ) : (
            <span className="flex items-center gap-2 text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-brand live-dot" /> Checking every 5 seconds
            </span>
          )}
          {!connected && (
            <button onClick={reload} disabled={checking} className="inline-flex items-center gap-1.5 h-10 px-2 rounded-md text-slate-300 hover:text-white transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60">
              <RefreshCw size={12} className={checking ? 'animate-spin' : ''} /> Check now
            </button>
          )}
        </div>
      </div>

      {!connected && (
        <div className="mt-8">
          <p className="text-[13px] font-medium text-slate-300">Still waiting after a minute? Check these, in order:</p>
          <ol className="mt-4 space-y-3">
            {[
              [KeyRound, <>The token is in <span className="font-mono text-slate-300">licence_key</span>, you pressed <span className="text-slate-300">Save</span>, and then restarted the add-on.</>],
              [ScrollText, <>The add-on's <span className="text-slate-300">Log</span> tab. It says in plain words what happened with the licence.</>],
              [Wifi, <>Home Assistant can reach the internet. It only needs to for this one check.</>],
            ].map(([Icon, text], i) => (
              <li key={i} className="flex gap-3.5 text-[13px] text-slate-400 leading-relaxed">
                <span className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/[0.07] flex items-center justify-center shrink-0">
                  <Icon size={13} className="text-slate-400" />
                </span>
                <span className="pt-1">{text}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="flex items-center justify-between gap-4 mt-12 pt-6 border-t border-white/[0.06]">
        <span />
        {connected ? (
          <button onClick={onNext} className="btn-primary">Finish setup <ArrowRight size={15} /></button>
        ) : (
          <button onClick={onNext} className="btn-secondary">I'll do this later <ArrowRight size={14} /></button>
        )}
      </div>
    </>
  )
}

/* ── 6. Done ────────────────────────────────────────────────────────── */

function DoneStep() {
  const next = [
    { icon: Cpu, title: 'Open FiremeX in Home Assistant', text: 'It is in the sidebar. Your cameras and their status are there.' },
    { icon: Users, title: 'Invite your team', text: 'Give colleagues their own login to this account.', to: '/settings/team' },
    { icon: CreditCard, title: 'Review your plan', text: 'Upgrade, change card or download invoices.', to: '/billing' },
  ]
  return (
    <>
      <div className="relative w-16 h-16 mb-8">
        <span aria-hidden className="absolute inset-0 rounded-2xl bg-safe/20 blur-xl" />
        <div className="relative w-16 h-16 rounded-2xl bg-safe/15 border border-safe/30 flex items-center justify-center">
          <Check size={30} className="text-safe" strokeWidth={2.5} />
        </div>
      </div>
      <Title sub="FiremeX is watching your cameras inside Home Assistant now. This website looks after your account, token and plan.">
        You're all set.
      </Title>

      <div className="grid sm:grid-cols-3 gap-4">
        {next.map(({ icon: Icon, title, text, to }) => {
          const body = (
            <>
              <Icon size={17} className="text-brand" />
              <p className="text-[13.5px] text-slate-200 font-medium mt-4">{title}</p>
              <p className="text-[12.5px] text-slate-400 mt-1 leading-relaxed">{text}</p>
            </>
          )
          return to ? (
            <Link key={title} to={to} className="rounded-xl border border-white/[0.07] bg-panel/70 p-5 hover:border-white/[0.16] transition-colors">{body}</Link>
          ) : (
            <div key={title} className="rounded-xl border border-white/[0.07] bg-panel/70 p-5">{body}</div>
          )
        })}
      </div>

      <Link to="/" className="btn-primary mt-10">
        Go to my account <ArrowRight size={15} />
      </Link>
    </>
  )
}
