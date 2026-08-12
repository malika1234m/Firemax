import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Camera, Server, Terminal, Home, Bell, Check, Copy, ArrowRight,
  ChevronDown, CheckCircle2, ShieldCheck,
} from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { useSetupProgress } from '../hooks/useSetupProgress'

// The agent reaches the cloud through this app's own /api prefix, which nginx
// proxies to the control plane. Deriving it from the browser's location means
// the snippet below is correct on any deployment without being configured.
const CLOUD_URL = `${window.location.origin}/api`

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
      className="flex items-center gap-1.5 text-[11px] text-slate-400 border border-white/[0.1] rounded-lg px-2.5 py-1.5 bg-panel/80 backdrop-blur hover:bg-white/[0.06] transition-colors shrink-0"
    >
      {copied ? <><Check size={12} className="text-safe" /> Copied</> : <><Copy size={12} /> Copy</>}
    </button>
  )
}

function Snippet({ label, code }) {
  return (
    <div className="space-y-1.5">
      {label && <p className="text-[11px] text-slate-500 font-medium">{label}</p>}
      <div className="relative">
        <pre className="font-mono text-[11.5px] leading-relaxed text-slate-300 bg-black/40 border border-white/[0.08] rounded-lg p-3 pr-24 overflow-x-auto">{code}</pre>
        <div className="absolute top-2 right-2"><CopyButton text={code} /></div>
      </div>
    </div>
  )
}

/** One accordion row. Collapsed rows stay one line tall so the whole journey
 *  is visible at a glance; only the step being worked on shows its detail. */
function Step({ index, total, icon: Icon, title, summary, done, active, optional, open, onToggle, children }) {
  return (
    <div className="relative pl-9">
      {/* spine */}
      {index < total - 1 && (
        <span className={`absolute left-[15px] top-9 bottom-[-12px] w-px ${done ? 'bg-safe/25' : 'bg-white/[0.07]'}`} />
      )}
      {/* marker */}
      <span className={`absolute left-0 top-2.5 w-[31px] h-[31px] rounded-full border flex items-center justify-center
        ${done   ? 'bg-safe/10 border-safe/30'
        : active ? 'bg-brand/12 border-brand/40'
                 : 'bg-panel border-white/[0.08]'}`}>
        {done
          ? <Check size={14} className="text-safe" strokeWidth={3} />
          : <Icon size={14} className={active ? 'text-brand' : 'text-slate-600'} />}
      </span>

      <div className={`glass-card rounded-xl border transition-colors
        ${open ? 'border-white/[0.12]' : 'border-white/[0.06] hover:border-white/[0.1]'}`}>
        <button onClick={onToggle} className="w-full flex items-center gap-3 text-left px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[13px] font-medium ${done ? 'text-slate-500' : 'text-slate-200'}`}>{title}</span>
              {optional && <span className="text-[10px] text-slate-600 border border-white/[0.08] rounded px-1.5 py-0.5">optional</span>}
              {done && <span className="text-[10px] text-safe">done</span>}
              {active && !done && <span className="text-[10px] text-brand">you're here</span>}
            </div>
            {!open && <p className="text-[11.5px] text-slate-600 mt-0.5 truncate">{summary}</p>}
          </div>
          <ChevronDown size={15} className={`text-slate-600 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
        {open && (
          <div className="px-4 pb-4 pt-1 space-y-3 text-[12px] text-slate-500 leading-relaxed border-t border-white/[0.05]">
            {children}
          </div>
        )}
      </div>
    </div>
  )
}

export default function GetStarted() {
  const { steps, doneCount, total, currentIndex, complete, haLinked, loading } = useSetupProgress()

  // `undefined` means "follow progress"; once the user clicks a row we respect
  // their choice instead of yanking the panel around under them on each poll.
  const [override, setOverride] = useState(undefined)
  const autoId = complete ? null : steps[currentIndex]?.id
  const openId = override === undefined ? autoId : override
  const toggle = (id) => setOverride(openId === id ? null : id)

  const isDone = (id) => steps.find(s => s.id === id)?.done
  const stepProps = (id, i) => ({
    index: i, total: 5,
    done: isDone(id), active: !complete && steps[currentIndex]?.id === id,
    open: openId === id, onToggle: () => toggle(id),
  })

  const envFile = `FIREMEX_CLOUD_URL=${CLOUD_URL}
AGENT_TOKEN=<paste your site token here>
DETECTOR_MODE=yolo
MODEL_PATH=/app/models/fire_model.pt`

  const composeFile = `services:
  agent:
    image: ghcr.io/malika1234m/firemex-agent:latest
    restart: unless-stopped
    env_file: ./edge.env
    volumes: [agent_models:/app/models]
volumes:
  agent_models:`

  return (
    <div className="max-w-3xl space-y-5 fade-up">
      <PageHeader title="Get Started" subtitle="Four steps to a working fire-detection site" />

      {/* progress */}
      <div className="glass-card border border-white/[0.09] rounded-xl p-4 space-y-2.5">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[12.5px] text-slate-200 font-medium">
            {loading ? 'Checking your setup…'
              : complete ? 'Setup complete'
              : `Step ${currentIndex + 1} of ${total} — ${steps[currentIndex].label}`}
          </p>
          <p className="text-[11px] text-slate-500 shrink-0">{doneCount}/{total}</p>
        </div>
        {/* segmented, so it reads as discrete steps rather than a vague percentage */}
        <div className="flex gap-1.5">
          {steps.map((s, i) => (
            <div key={s.id} className={`h-1.5 flex-1 rounded-full transition-colors
              ${s.done ? 'bg-safe' : i === currentIndex ? 'bg-brand' : 'bg-white/[0.08]'}`} />
          ))}
        </div>
      </div>

      <p className="text-[12px] text-slate-500 leading-relaxed">
        FiremeX runs detection on <span className="text-slate-300">your own hardware</span>. A small program —
        the edge agent — watches your cameras on your network and sends only detections here.
        Your video never leaves your site.
      </p>

      <div className="space-y-3">
        <Step {...stepProps('camera', 0)} icon={Camera}
              title="1. Add a camera"
              summary="Register the cameras FiremeX should watch">
          <p>Tell FiremeX which cameras exist. A camera is normally an RTSP stream from your CCTV system.</p>
          <p className="text-slate-600">
            No CCTV yet? Use any <code className="font-mono text-slate-400">https://…mp4</code> video URL as the
            stream — it behaves exactly like a camera and needs no hardware.
          </p>
          <Link to="/cameras" className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline">
            Go to Cameras <ArrowRight size={12} />
          </Link>
        </Step>

        <Step {...stepProps('site', 1)} icon={Server}
              title="2. Create a site"
              summary="Get the enrollment token your agent logs in with">
          <p>A site is one building running one agent. Creating it gives you an <span className="text-slate-300">enrollment token</span> — the agent's password.</p>
          <p className="text-slate-600">It is shown once. If you lose it, press Rotate token for a new one — the old one stops working immediately.</p>
          <Link to="/sites" className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline">
            Go to Sites <ArrowRight size={12} />
          </Link>
        </Step>

        <Step {...stepProps('agent', 2)} icon={Terminal}
              title="3. Run the edge agent"
              summary="Two files and one command on a computer at your site">
          <p>On any always-on computer at your site with Docker installed, save these two files in one folder.</p>
          <Snippet label="edge.env" code={envFile} />
          <Snippet label="docker-compose.yml" code={composeFile} />
          <Snippet label="Check the connection, then start it" code={`docker compose run --rm agent python agent.py --selftest\ndocker compose up -d`} />
          <p className="text-slate-600">
            The self-test needs no cameras — it only proves the token and address are right, so a
            connection problem never looks like a camera problem. Once started, this page ticks over
            within about 10 seconds.
          </p>
        </Step>

        <Step {...stepProps('alert', 3)} icon={Bell}
              title="4. See your first alert"
              summary="Detections arrive here with a snapshot">
          <p>When the agent sees fire or smoke, an alert appears with a snapshot of the moment it triggered.</p>
          <p className="text-slate-600">
            Alerts are raw detections. Nothing escalates on its own — a person reviews an alert and promotes
            it to an incident before any siren, call or automation runs.
          </p>
          <Link to="/alerts" className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline">
            Go to Alerts <ArrowRight size={12} />
          </Link>
        </Step>

        <Step index={4} total={5} icon={Home}
              title="Connect Home Assistant"
              summary="Optional — let confirmed incidents control lights, sirens and locks"
              done={haLinked} active={false} optional
              open={openId === 'ha'} onToggle={() => toggle('ha')}>
          <p>Link your Home Assistant so confirmed incidents can switch on lights, sirens or door locks, and push to your phone.</p>
          <p className="text-slate-600">
            You'll need its address and a long-lived access token
            (Home Assistant → your profile → Long-Lived Access Tokens → Create).
          </p>
          <Link to="/settings/home-assistant" className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline">
            Home Assistant settings <ArrowRight size={12} />
          </Link>
        </Step>
      </div>

      {complete && (
        <div className="glass-card border border-safe/30 rounded-xl p-5 flex items-center gap-3">
          <CheckCircle2 size={18} className="text-safe shrink-0" />
          <div className="min-w-0">
            <p className="text-[13px] text-slate-200 font-medium">You're set up.</p>
            <p className="text-[11.5px] text-slate-500">
              Your site is online and detecting. Tune sensitivity in{' '}
              <Link to="/settings/detection" className="text-brand hover:underline">Settings → Detection</Link>.
            </p>
          </div>
        </div>
      )}

      <div className="flex items-start gap-2.5 text-[11.5px] text-slate-600 pt-1">
        <ShieldCheck size={14} className="text-slate-700 shrink-0 mt-0.5" />
        <p>
          Detection keeps running if your internet drops — events queue on the agent and are delivered
          when the connection returns.
        </p>
      </div>
    </div>
  )
}
