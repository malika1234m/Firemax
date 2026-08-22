import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell, ShieldCheck, Home, CalendarClock, Building2, ArrowRight, CheckCircle2,
  MonitorPlay, Boxes, Server, Factory, HeartPulse, GraduationCap, ShoppingBag,
  Flame, ScanEye, Video, LayoutDashboard, Camera, Sparkles, Rocket, Crown,
} from 'lucide-react'
import { apiFetch } from '../lib/api'
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
  { icon: ScanEye,      title: 'Real-Time AI Detection',        text: 'Every camera feed is analyzed live for fire, smoke, and hazard signatures — no waiting for someone to notice.' },
  { icon: Bell,         title: 'Instant Multi-Channel Alerts',  text: 'Push, SMS, and email fire the moment a hazard is detected, so the right person knows immediately.' },
  { icon: ShieldCheck,  title: 'Human-Confirmed Incidents',     text: 'Operators confirm a detection before automations run — cutting false-alarm noise without slowing real response.' },
  { icon: Home,         title: 'Home Assistant Automation',     text: 'A confirmed incident can unlock doors, cut power, or shut off HVAC through your existing smart devices.' },
  { icon: CalendarClock,title: 'Shift Scheduling & Accountability', text: 'Assign operator coverage and require a resolution note on every incident — true fire or false alarm, always logged.' },
  { icon: Building2,    title: 'Multi-Tenant & Secure',         text: 'Every organization\'s cameras, alerts, and users are fully isolated, with role-based access for admins and operators.' },
]

/* The install story, told the way most customers will actually live it: FiremeX
 * goes into the Home Assistant they already run. The old version of this
 * section showed an edge-agent CLI, which contradicted the hero and described
 * the path fewer customers take. The agent is still offered — one section
 * below, on its own terms — rather than being the default everyone reads. */
const STEPS = [
  {
    label: 'Add the FiremeX repository to Home Assistant',
    render: () => (
      <div className="rounded-lg bg-black/60 border border-white/[0.08] px-4 py-3 font-mono text-[12px]">
        <div className="text-slate-600 text-[11px] mb-1.5">Settings → Add-ons → Add-on Store → ⋮ → Repositories</div>
        <span className="text-brand break-all">https://github.com/malika1234m/Firemax</span>
      </div>
    ),
  },
  {
    label: 'Install FiremeX and press Start',
    render: () => (
      <div className="rounded-lg bg-black/60 border border-white/[0.08] px-4 py-3 font-mono text-[12px] leading-relaxed">
        <div className="text-slate-300">FiremeX Fire &amp; Smoke Detection (Local)</div>
        <div className="text-safe mt-1.5">✓ model verified · watching 4 cameras</div>
        <div className="text-slate-600 mt-1">dashboard, controls and automations created for you</div>
      </div>
    ),
  },
  {
    label: 'Confirm & automate response',
    render: () => (
      <div className="rounded-lg bg-black/60 border border-white/[0.08] px-4 py-3 font-mono text-[12px] leading-relaxed">
        <div><span className="text-ember">on</span> <span className="text-slate-300">incident</span>(<span className="text-brand">"fire"</span>) {'{'}</div>
        <div className="pl-4 text-slate-300">notify(operators, authorities)</div>
        <div className="pl-4 text-slate-300">homeAssistant.run(<span className="text-brand">"evacuation"</span>)</div>
        <div>{'}'}</div>
      </div>
    ),
  },
]

/* Both ways of running FiremeX, stated plainly. The add-on is the recommended
 * path and is listed first, but the agent is presented as a real product for
 * sites with no Home Assistant or with several buildings to cover — not as a
 * fallback for people who failed at the first one. */
const DEPLOYMENTS = [
  {
    icon: Home,
    badge: 'Recommended',
    title: 'Home Assistant add-on',
    tagline: 'You already run Home Assistant',
    points: [
      'Free for one camera — no account needed to try it',
      'Installs from the Add-on Store in three clicks',
      'Uses the cameras Home Assistant already has',
      'Runs fully local — works with no internet',
      'Alerts and controls appear in your HA dashboard',
    ],
    note: 'Requires Home Assistant OS or Supervised. A licence key lifts the one-camera limit.',
    accent: 'text-live',
    chip: 'bg-live/10 text-live border-live/25',
    hover: 'hover:border-live/30',
  },
  {
    icon: Server,
    badge: null,
    title: 'FiremeX edge agent',
    tagline: 'No Home Assistant, or several sites',
    points: [
      'Runs anywhere Docker runs',
      'Connects straight to RTSP, ONVIF and NVR cameras',
      'One dashboard across every building',
      'Incident history, users and shift scheduling',
    ],
    note: 'Requires a machine that stays on, on the camera network.',
    accent: 'text-brand',
    chip: 'bg-brand/10 text-brand border-brand/25',
    hover: 'hover:border-brand/30',
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
        <span className="mx-auto text-[11px] text-slate-500 font-medium">FiremeX · Live Monitoring</span>
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
              <p className="font-raj font-bold text-[15px] text-white">Live Feed</p>
              <p className="text-[11px] text-slate-600">6 cameras · 3 zones</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-[10px] font-medium text-safe bg-safe/10 border border-safe/25 rounded-md px-2 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-safe live-dot" /> LIVE
              </span>
              <span className="text-[10px] font-medium text-hazard bg-hazard/10 border border-hazard/25 rounded-md px-2 py-1">RISK: CRITICAL</span>
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
              <p className="text-[10px] text-slate-500">Awaiting operator confirmation</p>
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
            Simple pricing
          </span>
          <h2 className="font-raj font-extrabold text-[32px] sm:text-[40px] mt-5 leading-[1.05]">
            Plans that scale with your site
          </h2>
          <p className="text-slate-500 text-[14px] mt-3">
            Start free on the 14-day trial. Not sure which fits?{' '}
            <Link to="/request-demo" className="text-ember hover:text-ember/80 font-medium">Request a demo</Link>.
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
                  <span>{p.max_cameras} cameras</span>
                  <span className="w-1 h-1 rounded-full bg-slate-700" />
                  <span>{p.max_users} users</span>
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
                  {isTrial ? 'Start Free Trial' : `Choose ${p.label}`}
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
            <Link to="/login" className="text-[13px] font-medium text-slate-300 hover:text-white transition-colors px-3 py-2">Sign In</Link>
            <Link to="/signup" className="text-[13px] font-medium bg-ember text-white px-4 py-2 rounded-lg hover:bg-ember-dark transition-colors">Get Started</Link>
          </div>
        </div>
      </header>

      {/* ── Hero (centered) ─────────────────────────────── */}
      <section className="relative">
        {/* navy radial glow behind hero */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[720px] bg-[radial-gradient(60%_60%_at_50%_0%,rgba(37,52,92,0.55),transparent_70%)]" />
        <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-24 w-[40rem] h-[24rem] rounded-full bg-ember/10 blur-[130px]" />

        <div className="relative max-w-4xl mx-auto px-6 sm:px-10 pt-20 pb-10 text-center">
          {/* FiremeX is primarily a Home Assistant add-on, and the hero says so.
              Most prospects already run Home Assistant watching their building;
              telling them up front that this installs into it — rather than
              being another system to run — is the single most useful thing on
              the page. The standalone agent is named too, so nobody without
              Home Assistant assumes the product is closed to them. */}
          <div className="inline-flex items-center gap-2 text-[12px] font-semibold tracking-wide
                          text-live bg-live/10 border border-live/25 rounded-full px-3 py-1.5 mb-6">
            <Home size={13} /> Runs as a Home Assistant add-on
          </div>
          <h1 className="font-raj font-extrabold text-[44px] sm:text-[58px] lg:text-[64px] leading-[1.02] tracking-tight">
            <span className="text-ember">Fire Detection</span> inside Home Assistant
          </h1>
          <p className="text-slate-300 text-[15px] sm:text-[17px] mt-6 max-w-2xl mx-auto leading-relaxed">
            FiremeX installs into the Home Assistant you already run and watches the cameras it
            already has. Detection happens on your own hardware —{' '}
            <span className="inline-flex items-center text-[13px] font-mono text-brand bg-brand/10 border border-brand/25 rounded-md px-2 py-0.5 align-middle">video never leaves your network</span>.
            {' '}No Home Assistant? A standalone agent does the same job on any machine.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-8">
            <Link to="/signup" className="flex items-center gap-2 bg-ember text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-ember-dark transition-colors">
              Get Started for Free <ArrowRight size={15} />
            </Link>
            <Link to="/request-demo" className="flex items-center gap-2 bg-white/[0.06] border border-white/15 text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-white/10 transition-colors">
              Request a Demo <ArrowRight size={15} />
            </Link>
          </div>
        </div>

        {/* ── Product preview ── */}
        <div className="relative max-w-5xl mx-auto px-6 sm:px-10 pb-20">
          <ProductPreview />
        </div>
      </section>

      {/* ── Social proof ────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-6 sm:px-10 py-16 text-center">
        <h2 className="font-raj font-extrabold text-[30px] sm:text-[40px] leading-[1.08]">
          Production-ready monitoring<br /><span className="text-ember">built for your facility</span>
        </h2>
        <p className="text-slate-500 text-[14px] mt-4 max-w-xl mx-auto">
          Trusted by safety teams across the highest-risk industries to catch fire before it spreads.
        </p>
        <div className="grid grid-cols-3 lg:grid-cols-6 gap-6 mt-12 opacity-70">
          {INDUSTRIES.map(({ icon: Icon, label }) => (
            <div key={label} className="flex flex-col items-center gap-2 text-slate-500">
              <Icon size={26} strokeWidth={1.4} />
              <span className="text-[12px] font-medium tracking-wide">{label}</span>
            </div>
          ))}
        </div>
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
            Conventional detectors wait for smoke to reach a sensor. FiremeX sees the flame the instant a camera
            does — and delivers a human-confirmed incident in under two seconds.
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
            Three steps inside Home Assistant — no rip-and-replace hardware, no new box to run.
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

      {/* ── Two ways to run ─────────────────────────────── */}
      <section className="border-t border-white/[0.06] bg-panel/40">
        <div className="max-w-5xl mx-auto px-6 sm:px-10 py-20">
          <div className="text-center max-w-xl mx-auto mb-12">
            <h2 className="font-raj font-extrabold text-[28px] sm:text-[36px] leading-[1.08]">
              Two ways to run it. <span className="text-ember">Same detection.</span>
            </h2>
            <p className="text-slate-500 text-[14px] mt-4">
              The model, the confirmation workflow and the automations are identical. All that
              changes is what you install and where you review alerts.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            {DEPLOYMENTS.map(({ icon: Icon, badge, title, tagline, points, note, accent, chip, hover }) => (
              <div key={title}
                   className={`glass-card border border-white/[0.07] rounded-xl p-6 flex flex-col transition-colors ${hover}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="w-10 h-10 rounded-lg bg-white/[0.04] border border-white/[0.07] flex items-center justify-center shrink-0">
                    <Icon size={18} className={accent} />
                  </div>
                  {badge && (
                    <span className={`text-[10px] font-semibold tracking-wider uppercase px-2 py-1 rounded-full border ${chip}`}>
                      {badge}
                    </span>
                  )}
                </div>

                <h3 className="font-raj font-bold text-[20px] text-white mt-4">{title}</h3>
                <p className={`text-[12px] font-medium mt-1 ${accent}`}>{tagline}</p>

                <ul className="mt-5 space-y-2.5 flex-1">
                  {points.map(pt => (
                    <li key={pt} className="flex items-start gap-2.5 text-[13.5px] text-slate-300">
                      <CheckCircle2 size={15} className={`${accent} mt-0.5 shrink-0`} />
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>

                <p className="text-[11.5px] text-slate-600 mt-5 leading-relaxed">{note}</p>
              </div>
            ))}
          </div>

          <p className="text-center text-[13px] text-slate-500 mt-8">
            Not sure which fits? We ask once when you sign up, then show you only the steps that apply.
          </p>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 sm:px-10 py-20 border-t border-white/[0.06]">
        <div className="text-center max-w-xl mx-auto mb-14">
          <h2 className="font-raj font-bold text-[28px] sm:text-[32px]">Everything a safety team needs, in one system</h2>
          <p className="text-slate-500 text-[14px] mt-3">Built for facilities that can't afford to find out about a fire late.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-3 hover:border-ember/30 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-ember/10 border border-ember/20 flex items-center justify-center">
                <Icon size={18} className="text-ember" />
              </div>
              <h3 className="font-raj font-semibold text-[15px] text-white">{title}</h3>
              <p className="text-[13px] text-slate-500 leading-relaxed">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Command-center showcase ─────────────────────── */}
      <section className="bg-panel border-y border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 sm:px-10 py-20 grid lg:grid-cols-2 gap-12 items-center">
          <div className="relative order-2 lg:order-1">
            <div className="absolute -inset-3 bg-gradient-to-br from-ember/15 to-brand/15 blur-2xl rounded-3xl" />
            <div className="relative rounded-2xl overflow-hidden border border-white/[0.09] shadow-2xl shadow-black/60">
              <img src={landingOps} alt="FiremeX operations center" className="w-full object-cover" />
            </div>
          </div>
          <div className="order-1 lg:order-2">
            <span className="inline-flex items-center gap-2 text-[11px] font-medium tracking-[0.08em] uppercase text-brand bg-brand/10 border border-brand/25 rounded-full px-3 py-1.5">
              <MonitorPlay size={12} /> One command center
            </span>
            <h2 className="font-raj font-bold text-[28px] sm:text-[34px] mt-5 leading-tight">Every camera, every zone — on one screen</h2>
            <p className="text-slate-400 text-[15px] mt-4 leading-relaxed">
              Live feeds, floor-plan hazard maps, thermal views, and a full incident log in a single operator
              dashboard. When a camera flags fire, the whole team sees exactly where, when, and how confident.
            </p>
            <ul className="mt-6 space-y-3">
              {['Tiled & pinnable live feeds', 'Floor-plan hazard mapping', 'Full incident & resolution audit trail'].map(item => (
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
          <h2 className="font-raj font-bold text-[28px] sm:text-[34px]">Ready to protect your facility?</h2>
          <p className="text-slate-400 text-[14px] mt-3 max-w-lg mx-auto">
            Start monitoring in minutes, or talk to us first — either way, we'll show you exactly what your team sees.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-8">
            <Link to="/signup" className="flex items-center gap-2 bg-ember text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-ember-dark transition-colors">
              Get Started <ArrowRight size={15} />
            </Link>
            <Link to="/request-demo" className="flex items-center gap-2 border border-white/15 text-white text-sm font-semibold px-6 py-3 rounded-lg hover:bg-white/5 transition-colors">
              Request a Demo
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
          <p className="text-[12px] text-slate-700">© {new Date().getFullYear()} FiremeX. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
