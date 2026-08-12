import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Camera, Server, Terminal, Home, Bell, CheckCircle2, Circle, Copy, ArrowRight } from 'lucide-react'
import { apiFetch } from '../lib/api'
import PageHeader from '../components/PageHeader'

// The agent reaches the cloud through this app's own /api prefix, which nginx
// proxies to the control plane. Deriving it from the browser's location means
// the snippet below is correct on any deployment without being configured.
const CLOUD_URL = `${window.location.origin}/api`

function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
      className="flex items-center gap-1.5 text-[11px] text-slate-400 border border-white/[0.1] rounded-lg px-2.5 py-1.5 hover:bg-white/[0.04] transition-colors shrink-0"
    >
      {copied ? <><CheckCircle2 size={12} className="text-safe" /> Copied</> : <><Copy size={12} /> {label}</>}
    </button>
  )
}

function Snippet({ code }) {
  return (
    <div className="relative group">
      <pre className="font-mono text-[11.5px] leading-relaxed text-slate-300 bg-black/40 border border-white/[0.08] rounded-lg p-3 pr-20 overflow-x-auto">{code}</pre>
      <div className="absolute top-2 right-2"><CopyButton text={code} /></div>
    </div>
  )
}

function Step({ n, icon: Icon, title, done, optional, children }) {
  return (
    <div className="glass-card border border-white/[0.07] rounded-xl p-5 space-y-3">
      <div className="flex items-start gap-3">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border
          ${done ? 'bg-safe/10 border-safe/30' : 'bg-slate-900 border-white/[0.08]'}`}>
          {done ? <CheckCircle2 size={16} className="text-safe" /> : <Icon size={15} className="text-slate-500" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className={`text-[13px] font-medium ${done ? 'text-slate-400 line-through decoration-slate-700' : 'text-slate-200'}`}>
              {n}. {title}
            </p>
            {optional && <span className="text-[10px] text-slate-600 border border-white/[0.08] rounded px-1.5 py-0.5">optional</span>}
            {done && <span className="text-[10px] text-safe">done</span>}
          </div>
          <div className="mt-2.5 space-y-2.5 text-[12px] text-slate-500 leading-relaxed">{children}</div>
        </div>
      </div>
    </div>
  )
}

export default function GetStarted() {
  const [cameras, setCameras] = useState([])
  const [sites,   setSites]   = useState([])
  const [alerts,  setAlerts]  = useState([])
  const [ha,      setHa]      = useState(null)

  const load = () => {
    apiFetch('/cameras/').then(r => r.ok ? r.json() : []).then(setCameras).catch(() => {})
    apiFetch('/sites/').then(r => r.ok ? r.json() : []).then(setSites).catch(() => {})
    apiFetch('/alerts/?limit=1').then(r => r.ok ? r.json() : []).then(setAlerts).catch(() => {})
    apiFetch('/ha/config').then(r => r.ok ? r.json() : null).then(setHa).catch(() => {})
  }

  // Polled so the checklist ticks over on its own while the user is following
  // it in another window — the agent coming online is the moment that matters.
  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id) }, [])

  const hasCamera  = cameras.length > 0
  const hasSite    = sites.length > 0
  const agentOnline = sites.some(s => s.status === 'online')
  const haLinked   = Boolean(ha?.ha_url)
  const hasAlert   = alerts.length > 0

  const core = [hasCamera, hasSite, agentOnline, hasAlert]
  const doneCount = core.filter(Boolean).length

  const envFile = `FIREMEX_CLOUD_URL=${CLOUD_URL}
AGENT_TOKEN=<paste your site token here>
DETECTOR_MODE=yolo
MODEL_PATH=/app/models/fire_model.pt`

  return (
    <div className="max-w-3xl space-y-5 fade-up">
      <PageHeader title="Get Started" subtitle="Five steps to a working fire-detection site" />

      {/* progress */}
      <div className="glass-card border border-white/[0.09] rounded-xl p-4 flex items-center gap-4">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-[12px] text-slate-300 font-medium">Setup progress</p>
            <p className="text-[11px] text-slate-500">{doneCount} of {core.length}</p>
          </div>
          <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
            <div className="h-full bg-brand transition-all duration-500" style={{ width: `${(doneCount / core.length) * 100}%` }} />
          </div>
        </div>
      </div>

      <p className="text-[12px] text-slate-500 leading-relaxed">
        FiremeX runs detection on <span className="text-slate-300">your own hardware</span>. A small program — the
        edge agent — watches your cameras on your network and sends only detections here.
        Your video never leaves your site.
      </p>

      <Step n={1} icon={Camera} title="Add a camera" done={hasCamera}>
        <p>Tell FiremeX which cameras exist. A camera is normally an RTSP stream from your CCTV system.</p>
        <p className="text-slate-600">
          No CCTV yet? Use any <code className="font-mono text-slate-400">https://…mp4</code> video URL as the stream —
          it works exactly like a camera and needs no hardware.
        </p>
        <Link to="/cameras" className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline">
          Go to Cameras <ArrowRight size={12} />
        </Link>
      </Step>

      <Step n={2} icon={Server} title="Create a site" done={hasSite}>
        <p>A site is one building running one agent. Creating it gives you an <span className="text-slate-300">enrollment token</span> — the agent's password.</p>
        <p className="text-slate-600">It is shown once. If you lose it, press Rotate token to get a new one.</p>
        <Link to="/sites" className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline">
          Go to Sites <ArrowRight size={12} />
        </Link>
      </Step>

      <Step n={3} icon={Terminal} title="Run the edge agent" done={agentOnline}>
        <p>On any always-on computer at your site with Docker installed, save these two files in one folder.</p>

        <p className="text-slate-400 font-medium mt-3">edge.env</p>
        <Snippet code={envFile} />

        <p className="text-slate-400 font-medium mt-3">docker-compose.yml</p>
        <Snippet code={`services:
  agent:
    image: ghcr.io/malika1234m/firemex-agent:latest
    restart: unless-stopped
    env_file: ./edge.env
    volumes: [agent_models:/app/models]
volumes:
  agent_models:`} />

        <p className="text-slate-400 font-medium mt-3">Then check the connection, and start it</p>
        <Snippet code={`docker compose run --rm agent python agent.py --selftest
docker compose up -d`} />

        <p className="text-slate-600">
          The self-test needs no cameras — it just proves the token and URL are right.
          Once started, this page ticks over to done within about 10 seconds.
        </p>
      </Step>

      <Step n={4} icon={Home} title="Connect Home Assistant" done={haLinked} optional>
        <p>Link your Home Assistant so confirmed incidents can switch on lights, sirens or door locks, and push to your phone.</p>
        <p className="text-slate-600">
          You need your Home Assistant address and a long-lived access token
          (Home Assistant → your profile → Long-Lived Access Tokens → Create).
        </p>
        <Link to="/settings/home-assistant" className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline">
          Home Assistant settings <ArrowRight size={12} />
        </Link>
      </Step>

      <Step n={5} icon={Bell} title="See your first alert" done={hasAlert}>
        <p>When the agent sees fire or smoke, an alert appears here with a snapshot of the moment it triggered.</p>
        <p className="text-slate-600">
          Alerts are raw detections. Nothing is escalated automatically — a person reviews an alert and
          promotes it to an incident before any siren, call or automation runs.
        </p>
        <Link to="/alerts" className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline">
          Go to Alerts <ArrowRight size={12} />
        </Link>
      </Step>

      {doneCount === core.length && (
        <div className="glass-card border border-safe/30 rounded-xl p-5 flex items-center gap-3">
          <CheckCircle2 size={18} className="text-safe shrink-0" />
          <div>
            <p className="text-[13px] text-slate-200 font-medium">You're set up.</p>
            <p className="text-[11.5px] text-slate-500">Your site is online and detecting. Tune sensitivity in Settings → Detection.</p>
          </div>
        </div>
      )}
    </div>
  )
}
