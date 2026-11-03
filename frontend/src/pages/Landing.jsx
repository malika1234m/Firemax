import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell, ShieldCheck, Home, ArrowRight, CheckCircle2, MonitorPlay, Boxes, Server, Factory, HeartPulse, GraduationCap, ShoppingBag, Flame, ScanEye, Video, LayoutDashboard, Camera, Sparkles, Rocket, Crown, Lock, Store, ExternalLink,
} from 'lucide-react'
import { apiFetch } from '../lib/api'
import { OPEN_ADDON_URL, WHATS_NEW } from '../lib/homeAssistant'
import landingOps from '../assets/landing-ops.png'
import logo from '../assets/logo.png'

const PLAN_ICON = { trial: Sparkles, starter: Rocket, pro: Crown }

const INDUSTRIES = [
  { icon: Boxes,         label: 'Warehousing' },
  { icon: Server,        label: 'Data Centers' },
  { icon: Factory,       label: 'Manufacturing' },
  { icon: HeartPulse,    label: 'Healthcare' },
  { icon: GraduationCap, label: 'Campuses' },
  { icon: ShoppingBag,   label: 'Retail' },
]

const FEATURES = [
  { icon: ScanEye,     title: 'Fire, smoke and small flames', text: 'A YOLO26 model trained on real fires and our own camera footage. A lighter or candle is recognised as a small flame — and never raises a false alarm.' },
  { icon: Home,        title: 'Inside Home Assistant',        text: 'Uses the cameras Home Assistant already has, including encrypted EZVIZ cameras. Nothing new to run, no camera passwords entered twice.' },
  { icon: ShieldCheck, title: 'Human-confirmed incidents',    text: 'An alert shows the photo FiremeX reacted to. Sprinklers, sirens and call-outs wait for a person to press "Yes, it is a real fire".' },
  { icon: Bell,        title: 'Alerts on your phone',         text: 'Every alert and incident reaches the Home Assistant app on your phone, and the Emergency tab shows exactly which camera sees fire.' },
  { icon: Video,       title: 'Built for many cameras',       text: 'A compact camera wall with alerting cameras on top, and one shared checking budget so twenty cameras on a Raspberry Pi all stay current.' },
  { icon: Lock,        title: 'Video never leaves your network', text: 'Detection runs on your own hardware and keeps working without internet. Your FiremeX account only handles the subscription and token.' },
]

// What a customer actually lives through on the day — told plainly, because
// "what happens to me" matters more to a buyer than a feature list.
const STORY = [
  { icon: Flame, title: 'A camera sees flame or smoke',
    text: 'FiremeX keeps an eye on every camera, day and night. A lighter or candle is recognised as a small flame and left alone.' },
  { icon: Bell, title: 'Your phone tells you, with a photo',
    text: 'Through the Home Assistant app — so you see exactly what the camera saw, wherever you are.' },
  { icon: ShieldCheck, title: 'You decide what happens next',
    text: 'Press "yes, it is a real fire" and your sirens or sprinklers can take over. Nothing fires off on a guess.' },
]

/* The install story, as customers live it. Step 2 is one button: it opens the
 * visitor's own Home Assistant on the FiremeX add-on and offers to add the
 * repository with the address already typed in. */
const STEPS = [
  {
    label: 'Create your FiremeX account',
    render: () => (
      <div className="rounded-lg bg-black/60 border border-white/[0.08] px-4 py-3 text-[12.5px] leading-relaxed">
        <div className="text-slate-300">Choose a plan and copy your access token.</div>
        <div className="font-mono text-brand mt-1.5">fmx_••••••••••••••••a91c</div>
      </div>
    ),
  },
  {
    label: 'One click opens the add-on store in your Home Assistant',
    render: () => (
      <div className="rounded-lg bg-black/60 border border-white/[0.08] px-4 py-3 text-[12.5px] leading-relaxed space-y-2.5">
        <a href={OPEN_ADDON_URL} target="_blank" rel="noreferrer"
           className="inline-flex items-center gap-2 bg-ember text-white text-[12.5px] font-semibold px-3.5 py-2 rounded-lg hover:bg-ember-dark transition-colors">
          <Store size={14} /> Open in Home Assistant <ExternalLink size={12} />
        </a>
        <div className="text-slate-500">The FiremeX repository address is filled in for you — press Add, then Install.</div>
      </div>
    ),
  },
  {
    label: 'Paste your token and press Start',
    render: () => (
      <div className="rounded-lg bg-black/60 border border-white/[0.08] px-4 py-3 font-mono text-[12px] leading-relaxed">
        <div className="text-slate-300">licence_key: <span className="text-brand">fmx_••••a91c</span></div>
        <div className="text-safe mt-1.5">✓ model verified · watching 4 cameras</div>
        <div className="text-slate-600 mt-1">FiremeX dashboard created in your sidebar</div>
      </div>
    ),
  },
]

function ProductPreview() {
  return (
    <div className="rounded-2xl overflow-hidden border border-white/[0.1] shadow-2xl shadow-black/60 bg-panel">
      {/* browser chrome */}
      <div className="flex items-center gap-2 h-9 px-4 bg-black/40 border-b border-white/[0.06]">
        <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
        <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
        <span className="w-3 h-3 rounded-full bg-[#28c840]" />
        <span className="mx-auto text-[11px] text-slate-500 font-medium">Home Assistant · FiremeX dashboard</span>
      </div>

      {/* app body */}
      <div className="flex">
        {/* mini sidebar */}
        <div className="hidden sm:flex flex-col items-center gap-4 py-5 px-3 bg-void/60 border-r border-white/[0.06]">
          <img src={logo} alt="" className="w-7 h-7 rounded-md" />
          {[LayoutDashboard, Video, Bell, Camera].map((Icon, i) => (
            <Icon key={i} size={16} className={i === 1 ? 'text-brand' : 'text-slate-600'} />
          ))}
        </div>

        <div className="flex-1 min-w-0 p-4 sm:p-5">
          {/* top bar */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-raj font-bold text-[15px] text-white">Home</p>
              <p className="text-[11px] text-slate-600">6 cameras · all others clear</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-[10px] font-medium text-safe bg-safe/10 border border-safe/25 rounded-md px-2 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-safe live-dot" /> LIVE
              </span>
              <span className="text-[10px] font-medium text-hazard bg-hazard/10 border border-hazard/25 rounded-md px-2 py-1">Fire seen on 1 camera</span>
            </div>
          </div>

          {/* camera grid */}
          <div className="grid grid-cols-3 gap-2.5">
            {[
              { name: 'Warehouse A', fire: false },
              { name: 'Loading Bay', fire: true },
              { name: 'Server Room', fire: false },
              { name: 'Main Entrance', fire: false },
              { name: 'Roof Deck', fire: false },
              { name: 'Parking', fire: false },
            ].map((cam) => (
              <div key={cam.name}
                   className={`relative aspect-video rounded-lg overflow-hidden border
                     ${cam.fire
                       ? 'border-hazard/70 bg-gradient-to-br from-orange-900/50 to-slate-900'
                       : 'border-white/[0.06] bg-gradient-to-br from-slate-800 to-slate-900'}`}>
                {cam.fire && (
                  <>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Flame size={22} className="text-ember" />
                    </div>
                    <span className="absolute top-1.5 left-1.5 text-[8px] font-mono font-bold text-hazard bg-black/70 border border-hazard/50 rounded px-1.5 py-0.5">
                      FIRE DETECTED
                    </span>
                  </>
                )}
                <span className="absolute bottom-1.5 left-1.5 text-[8px] text-slate-400 font-medium">{cam.name}</span>
                {!cam.fire && <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-safe live-dot" />}
              </div>
            ))}
          </div>

          {/* alert strip */}
          <div className="mt-3 flex items-center gap-3 rounded-lg bg-hazard/[0.08] border border-hazard/25 px-3 py-2.5">
            <Flame size={15} className="text-hazard shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-slate-200 font-medium truncate">Fire detected — Loading Bay · 98% confidence</p>
              <p className="text-[10px] text-slate-500">Is it real? One tap to confirm</p>
            </div>
            <span className="text-[10px] font-semibold text-void bg-ember rounded-md px-2.5 py-1 shrink-0">Confirm</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function PricingSection() {
  const [plans, setPlans] = useState([])
  useEffect(() => {
    apiFetch('/billing/plans').then(r => r.ok ? r.json() : null).then(d => d && setPlans(d.plans)).catch(() => {})
  }, [])

  return (
    <section id="pricing" className="border-t border-white/[0.06]">
      <div className="max-w-7xl mx-auto px-6 sm:px-10 py-24">
        <div className="text-center max-w-xl mx-auto mb-14">
          <span className="inline-flex items-center gap-2 text-[11px] font-medium tracking-[0.08em] uppercase text-ember bg-ember/10 border border-ember/25 rounded-full px-3 py-1.5">
            Pricing
          </span>
          <h2 className="font-raj font-extrabold text-[32px] sm:text-[40px] mt-5 leading-[1.05]">
            Simple, honest pricing
          </h2>
          <p className="text-slate-500 text-[14px] mt-3">
            Every camera is included. You pay for how many Home Assistants you run, and try it free for
            14 days first. Not sure which fits?{' '}
            <Link to="/request-demo" className="text-ember hover:text-ember/80 font-medium">Talk to us</Link>.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-5xl mx-auto">
          {plans.map(p => {
            const Icon = PLAN_ICON[p.plan_id] ?? Sparkles
            const isTrial = p.plan_id === 'trial'
            const popular = p.plan_id === 'starter'
            return (
              <div key={p.plan_id}
                   className={`glass-card rounded-xl p-6 flex flex-col gap-4 relative border
                     ${popular ? 'border-ember/40' : 'border-white/[0.07]'}`}>
                {popular && (
                  <span className="absolute -top-2.5 left-6 text-[9px] font-raj font-bold tracking-widest uppercase bg-ember text-white px-2 py-0.5 rounded-full">
                    Most Popular
                  </span>
                )}
                <div className="flex items-center gap-2.5">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0
                    ${popular ? 'bg-ember/15 text-ember' : 'bg-white/[0.04] text-slate-400'}`}>
                    <Icon size={16} />
                  </div>
                  <div>
                    <p className="font-raj font-semibold text-[15px] text-white capitalize">{p.label}</p>
                    <p className="font-raj font-bold text-[24px] text-white leading-none mt-0.5">
                      {isTrial ? 'Free' : `$${p.price_usd}`}
                      {!isTrial && <span className="text-[12px] text-slate-600 font-normal">/mo</span>}
                    </p>
                  </div>
                </div>

                <div className="text-[12px] text-slate-500 flex items-center gap-3 pb-3 border-b border-white/[0.06]">
                  <span>{p.max_installs} Home Assistant install{p.max_installs === 1 ? '' : 's'}</span>
                  <span className="w-1 h-1 rounded-full bg-slate-700" />
                  <span>unlimited cameras</span>
                </div>

                <ul className="space-y-2 text-[13px] text-slate-400 flex-1">
                  {p.features.map(f => (
                    <li key={f} className="flex items-start gap-2">
                      <CheckCircle2 size={14} className="text-ember shrink-0 mt-0.5" /> {f}
                    </li>
                  ))}
                </ul>

                <Link to="/signup"
                      className={`w-full text-center text-[13px] font-semibold py-2.5 rounded-lg transition-colors
                        ${popular ? 'bg-ember text-white hover:bg-ember-dark' : 'border border-white/15 text-white hover:bg-white/5'}`}>
                  {isTrial ? 'Start free' : `Choose ${p.label}`}
                </Link>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-void text-white overflow-x-hidden">
      {/* ── Top nav ─────────────────────────────────────── */}
      <header className="sticky top-0 z-30 backdrop-blur-md bg-void/70 border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 sm:px-10 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <img src={logo} alt="FiremeX" className="w-8 h-8 rounded-lg" />
            <span className="font-raj font-bold text-[18px]">Fireme<span className="text-ember">X</span></span>
          </div>
          <div className="flex items-center gap-3">
            <a href="#pricing" className="hidden sm:block text-[13px] font-medium text-slate-300 hover:text-white transition-colors px-3 py-2">Pricing</a>
            <Link to="/login" className="text-[13px] font-medium text-slate-300 hover:text-white transition-colors px-3 py-2">Sign in</Link>
            <Link to="/signup" className="text-[13px] font-medium bg-ember text-white px-4 py-2 rounded-lg hover:bg-ember-dark transition-colors">Start free</Link>
          </div>
        </div>
      </header>

      {/* ── Hero (centered) ─────────────────────────────── */}
      <section className="relative">
        {/* navy radial glow behind hero */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[720px] bg-[radial-gradient(60%_60%_at_50%_0%,rgba(37,52,92,0.55),transparent_70%)]" />
        <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-24 w-[40rem] h-[24rem] rounded-full bg-ember/10 blur-[130px]" />

        <div className="relative max-w-4xl mx-auto px-6 sm:px-10 pt-20 pb-10 text-center">
          {/* FiremeX is a Home Assistant add-on, and the hero says so first:
              it installs into the system people already run, rather than
              being another one to look after. */}
          <div className="inline-flex items-center gap-2 text-[12px] font-semibold tracking-wide
                          text-live bg-live/10 border border-live/25 rounded-full px-3 py-1.5 mb-6">
            <Home size={13} /> A Home Assistant add-on
          </div>
          <h1 className="font-raj font-extrabold text-[44px] sm:text-[58px] lg:text-[64px] leading-[1.02] tracking-tight">
            Your cameras, <span className="text-ember">watching for fire</span>
          </h1>
          <p className="text-slate-300 text-[15px] sm:text-[17px] mt-6 max-w-2xl mx-auto leading-relaxed">
            FiremeX is a small add-on for the Home Assistant you already run. It looks at the
            cameras you already have, and the moment it spots flame or smoke it tells you — with a
            photo, so you can decide in seconds. Everything happens on your own machine, so{' '}
            <span className="inline-flex items-center text-[13px] font-mono text-brand bg-brand/10 border border-brand/25 rounded-md px-2 py-0.5 align-middle">your video never leaves home</span>.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-8">
            <Link to="/signup" className="flex items-center gap-2 bg-ember text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-ember-dark transition-colors">
              Start free <ArrowRight size={15} />
            </Link>
            <Link to="/request-demo" className="flex items-center gap-2 bg-white/[0.06] border border-white/15 text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-white/10 transition-colors">
              Talk to us <ArrowRight size={15} />
            </Link>
          </div>
        </div>

        {/* ── Product preview ── */}
        <div className="relative max-w-5xl mx-auto px-6 sm:px-10 pb-20">
          <ProductPreview />
        </div>
      </section>

      {/* ── What happens when it sees fire ────────────── */}
      <section className="max-w-5xl mx-auto px-6 sm:px-10 py-16">
        <div className="text-center max-w-xl mx-auto">
          <h2 className="font-raj font-extrabold text-[30px] sm:text-[38px] leading-[1.08]">
            What happens when it <span className="text-ember">sees a fire</span>
          </h2>
          <p className="text-slate-500 text-[14px] mt-4">
            No jargon, no control room. Just the people who need to know, knowing.
          </p>
        </div>
        <ol className="grid md:grid-cols-3 gap-5 mt-12">
          {STORY.map(({ icon: Icon, title, text }, i) => (
            <li key={title} className="glass-card border border-white/[0.07] rounded-xl p-6">
              <div className="flex items-center gap-3">
                <span className="w-9 h-9 rounded-full bg-ember/12 border border-ember/30 flex items-center justify-center">
                  <Icon size={16} className="text-ember" />
                </span>
                <span className="text-[11px] font-mono text-slate-600">{i + 1}</span>
              </div>
              <h3 className="text-[15px] font-semibold text-white mt-4">{title}</h3>
              <p className="text-[13px] text-slate-400 mt-2 leading-relaxed">{text}</p>
            </li>
          ))}
        </ol>
        <p className="text-center text-[13px] text-slate-500 mt-10">
          Made for places where a fire would hurt most — {INDUSTRIES.map(i => i.label.toLowerCase()).join(', ')}.
        </p>
      </section>

      {/* ── Urgency ─────────────────────────────────────── */}
      <section className="relative overflow-hidden border-y border-white/[0.06] bg-panel/40">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-hazard/[0.05] to-transparent" />
        <div className="relative max-w-3xl mx-auto px-6 sm:px-10 py-20 text-center">
          <div className="w-14 h-14 rounded-2xl bg-hazard/10 border border-hazard/25 flex items-center justify-center mx-auto mb-6">
            <Flame size={24} className="text-hazard" />
          </div>
          <h2 className="font-raj font-bold text-[28px] sm:text-[38px] leading-[1.08]">A fire can double in size every 30 seconds.</h2>
          <p className="text-slate-400 text-[15px] sm:text-[17px] mt-5 leading-relaxed">
            A smoke detector waits for smoke to reach the ceiling. FiremeX looks at what your cameras
            already see, so you can hear about a flame while it is still small enough to put out.
          </p>
        </div>
      </section>

      {/* ── Get up and running (stepper) ────────────────── */}
      <section className="max-w-4xl mx-auto px-6 sm:px-10 py-24">
        <div className="text-center mb-16">
          <h2 className="font-raj font-extrabold text-[32px] sm:text-[44px] leading-[1.05]">
            <span className="text-ember">Get up</span> and running in minutes
          </h2>
          <p className="text-slate-500 text-[14px] mt-4">
            Three steps — no new hardware, no extra box to run. The only thing you type is your token.
          </p>
        </div>

        <div className="space-y-10">
          {STEPS.map((step, i) => (
            <div key={i} className="grid grid-cols-[auto_1fr] sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1.4fr)] gap-4 sm:gap-6 items-start">
              <p className="hidden sm:block text-right text-[14px] text-slate-300 font-medium pt-1.5">{step.label}</p>
              <div className="flex flex-col items-center">
                <span className="w-8 h-8 rounded-full bg-ember/15 border border-ember/40 text-ember font-mono text-[13px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                {i < STEPS.length - 1 && <span className="w-px flex-1 min-h-[48px] bg-white/[0.1] mt-1" />}
              </div>
              <div>
                <p className="sm:hidden text-[14px] text-slate-300 font-medium mb-2">{step.label}</p>
                {step.render()}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── What's new in the add-on ──────────────────── */}
      <section className="border-t border-white/[0.06] bg-panel/40">
        <div className="max-w-5xl mx-auto px-6 sm:px-10 py-20">
          <div className="text-center max-w-xl mx-auto mb-12">
            <h2 className="font-raj font-extrabold text-[28px] sm:text-[36px] leading-[1.08]">
              What's new in the <span className="text-ember">add-on</span>
            </h2>
            <p className="text-slate-500 text-[14px] mt-4">
              Updates arrive in Home Assistant as one Update button. Your settings are kept.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            {WHATS_NEW.map(r => (
              <div key={r.version} className="glass-card border border-white/[0.07] rounded-xl p-6">
                <span className="text-[11px] font-semibold tracking-wider uppercase px-2 py-1 rounded-full border bg-live/10 text-live border-live/25">
                  Version {r.version}
                </span>
                <ul className="mt-5 space-y-2.5">
                  {r.items.map(t => (
                    <li key={t} className="flex items-start gap-2.5 text-[13px] text-slate-300 leading-relaxed">
                      <CheckCircle2 size={15} className="text-live mt-0.5 shrink-0" />
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <p className="text-center text-[12.5px] text-slate-500 mt-8">
            Requires Home Assistant OS or Supervised. Free for one camera without a token.
          </p>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 sm:px-10 py-20 border-t border-white/[0.06]">
        <div className="text-center max-w-xl mx-auto mb-14">
          <h2 className="font-raj font-bold text-[28px] sm:text-[32px]">What FiremeX does for you</h2>
          <p className="text-slate-500 text-[14px] mt-3">Careful about real fires, calm about everything else.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-3 hover:border-ember/30 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-ember/10 border border-ember/20 flex items-center justify-center">
                <Icon size={18} className="text-ember" />
              </div>
              <h3 className="text-[15px] font-semibold text-white">{title}</h3>
              <p className="text-[13px] text-slate-500 leading-relaxed">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── The dashboard in Home Assistant ─────────────────────── */}
      <section className="bg-panel border-y border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 sm:px-10 py-20 grid lg:grid-cols-2 gap-12 items-center">
          <div className="relative order-2 lg:order-1">
            <div className="absolute -inset-3 bg-gradient-to-br from-ember/15 to-brand/15 blur-2xl rounded-3xl" />
            <div className="relative rounded-2xl overflow-hidden border border-white/[0.09] shadow-2xl shadow-black/60">
              <img src={landingOps} alt="The FiremeX dashboard" className="w-full object-cover" />
            </div>
          </div>
          <div className="order-1 lg:order-2">
            <span className="inline-flex items-center gap-2 text-[11px] font-medium tracking-[0.08em] uppercase text-brand bg-brand/10 border border-brand/25 rounded-full px-3 py-1.5">
              <MonitorPlay size={12} /> Your FiremeX dashboard
            </span>
            <h2 className="font-raj font-bold text-[28px] sm:text-[34px] mt-5 leading-tight">All your cameras on one calm screen</h2>
            <p className="text-slate-400 text-[15px] mt-4 leading-relaxed">
              The add-on puts a FiremeX dashboard in your Home Assistant sidebar — you don't build anything.
              Most days it simply says all is well. When a camera sees fire, it shows which one, the photo it
              reacted to, and a single button to say "yes, this is real".
            </p>
            <ul className="mt-6 space-y-3">
              {['Camera wall with alerting cameras on top', 'Emergency tab: where fire is seen, with photos', 'History with an evidence photo for every detection'].map(item => (
                <li key={item} className="flex items-center gap-2.5 text-[14px] text-slate-300">
                  <CheckCircle2 size={16} className="text-brand shrink-0" /> {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Pricing ─────────────────────────────────────── */}
      <PricingSection />

      {/* ── Final CTA ───────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-ember/[0.06] to-transparent" />
        <div className="relative max-w-4xl mx-auto px-6 sm:px-10 py-24 text-center">
          <h2 className="font-raj font-bold text-[28px] sm:text-[34px]">Try it on your own cameras</h2>
          <p className="text-slate-400 text-[14px] mt-3 max-w-lg mx-auto">
            The add-on watches one camera for free, with no account at all. When you're happy, create an
            account and it watches the rest. Questions first? We're glad to help.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-8">
            <Link to="/signup" className="flex items-center gap-2 bg-ember text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-ember-dark transition-colors">
              Create a free account <ArrowRight size={15} />
            </Link>
            <Link to="/request-demo" className="flex items-center gap-2 border border-white/15 text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-white/5 transition-colors">
              Talk to us
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────── */}
      <footer className="border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 sm:px-10 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <img src={logo} alt="FiremeX" className="w-6 h-6 rounded-md" />
            <span className="font-raj font-semibold text-[13px] text-slate-400">FiremeX</span>
          </div>
          <p className="text-[12px] text-slate-600">Fire detection for Home Assistant · © {new Date().getFullYear()} FiremeX</p>
        </div>
      </footer>
    </div>
  )
}
