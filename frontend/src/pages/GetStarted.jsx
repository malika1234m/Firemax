import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import {
  Camera, Server, Terminal, Home, Bell, Check, Copy, ArrowRight,
  ChevronDown, CheckCircle2, ShieldCheck, Download, AlertTriangle, Radio,
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

/** Saves text as a real file. The agent install depends on two files existing
 *  with EXACT names — a copy button leaves the customer to create them by hand,
 *  which is where a non-technical installer gets stuck (and "docker-compose.yml.txt"
 *  fails in a way that looks like a Docker problem, not a naming one). */
function DownloadButton({ text, filename }) {
  const save = () => {
    // application/octet-stream, NOT text/plain. Chrome appends an extension
    // when the filename's own extension doesn't match the MIME type, so
    // text/plain saved "edge.env" as "edge.env.txt" — and Finder hides known
    // extensions, so the file *looked* correct while Docker reported it
    // missing. An opaque type leaves the filename alone.
    const url = URL.createObjectURL(new Blob([text], { type: 'application/octet-stream' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }
  return (
    <button onClick={save}
            className="flex items-center gap-1.5 text-[11px] text-slate-400 border border-white/[0.1] rounded-lg px-2.5 py-1.5 bg-panel/80 backdrop-blur hover:bg-white/[0.06] transition-colors shrink-0">
      <Download size={12} /> Download
    </button>
  )
}

function Snippet({ label, code, filename }) {
  return (
    <div className="space-y-1.5">
      {label && (
        <p className="text-[11px] text-slate-500 font-medium">
          {label}{filename && <span className="text-slate-600"> — save as <code className="font-mono text-slate-400">{filename}</code></span>}
        </p>
      )}
      <div className="relative">
        <pre className={`font-mono text-[11.5px] leading-relaxed text-slate-300 bg-black/40 border border-white/[0.08] rounded-lg p-3 overflow-x-auto ${filename ? 'pr-[210px]' : 'pr-24'}`}>{code}</pre>
        <div className="absolute top-2 right-2 flex items-center gap-1.5">
          {filename && <DownloadButton text={code} filename={filename} />}
          <CopyButton text={code} />
        </div>
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

function StatRow({ icon: Icon, label, value, tone = 'default', to }) {
  const body = (
    <div className="flex items-center gap-2.5 py-1.5">
      <Icon size={13} className="text-slate-600 shrink-0" />
      <span className="text-[11.5px] text-slate-500 flex-1 min-w-0 truncate">{label}</span>
      <span className={`text-[11.5px] font-medium shrink-0 tabular-nums
        ${tone === 'safe' ? 'text-safe' : tone === 'muted' ? 'text-slate-600' : 'text-slate-300'}`}>
        {value}
      </span>
    </div>
  )
  return to
    ? <Link to={to} className="block -mx-2 px-2 rounded hover:bg-white/[0.03] transition-colors">{body}</Link>
    : body
}

/** Right-hand rail. Deliberately live data rather than decoration: during setup
 *  the question in someone's head is "did that work?", and these are the exact
 *  numbers that answer it without leaving the guide. */
function SidePanel({ counts, agentOnline, haLinked }) {
  return (
    <aside className="hidden xl:block w-[248px] shrink-0">
      <div className="sticky top-6 space-y-3">
        <div className="glass-card border border-white/[0.07] rounded-xl p-4">
          <p className="text-[10px] uppercase tracking-[0.08em] text-slate-600 font-semibold mb-1.5">Your setup</p>
          <div className="divide-y divide-white/[0.04]">
            <StatRow icon={Camera} label="Cameras" to="/cameras"
                     value={counts.cameras} tone={counts.cameras ? 'default' : 'muted'} />
            <StatRow icon={Server} label="Sites" to="/sites"
                     value={counts.sites} tone={counts.sites ? 'default' : 'muted'} />
            <StatRow icon={Radio} label="Edge agent"
                     value={agentOnline ? 'Online' : 'Offline'} tone={agentOnline ? 'safe' : 'muted'} />
            <StatRow icon={Bell} label="Alerts" to="/alerts"
                     value={counts.alertsCapped ? `${counts.alerts}+` : counts.alerts}
                     tone={counts.alerts ? 'default' : 'muted'} />
            <StatRow icon={Home} label="Home Assistant" to="/settings/home-assistant"
                     value={haLinked ? 'Linked' : 'Not set'} tone={haLinked ? 'safe' : 'muted'} />
          </div>
        </div>

        <div className="glass-card border border-white/[0.07] rounded-xl p-4 space-y-2">
          <p className="text-[10px] uppercase tracking-[0.08em] text-slate-600 font-semibold">Stuck?</p>
          <p className="text-[11.5px] text-slate-500 leading-relaxed">
            Run the self-test before anything else — it separates a connection problem from a
            camera problem in one command.
          </p>
          <pre className="font-mono text-[10.5px] text-slate-400 bg-black/40 border border-white/[0.07] rounded-lg p-2 overflow-x-auto">docker compose run --rm agent{'\n'}  python agent.py --selftest</pre>
          <Link to="/support" className="inline-flex items-center gap-1.5 text-[11.5px] text-brand hover:underline">
            Contact support <ArrowRight size={11} />
          </Link>
        </div>

        <div className="flex items-start gap-2 px-1">
          <ShieldCheck size={13} className="text-slate-700 shrink-0 mt-0.5" />
          <p className="text-[10.5px] text-slate-600 leading-relaxed">
            Detection runs on your hardware. Only detections and a thumbnail are uploaded.
          </p>
        </div>
      </div>
    </aside>
  )
}

export default function GetStarted() {
  const { steps, doneCount, total, currentIndex, complete, haLinked, counts, loading } = useSetupProgress()

  // `undefined` means "follow progress"; once the user clicks a row we respect
  // their choice instead of yanking the panel around under them on each poll.
  const [override, setOverride] = useState(undefined)

  // Which agent image to run and which weights it should fetch — owned by the
  // backend, not duplicated here. Null while loading; the snippets fall back to
  // sensible defaults so the page never renders half-built config.
  const [install, setInstall] = useState(null)
  useEffect(() => {
    apiFetch('/sites/agent-install')
      .then(r => (r.ok ? r.json() : null))
      .then(setInstall)
      .catch(() => {})
  }, [])

  const autoId = complete ? null : steps[currentIndex]?.id
  const openId = override === undefined ? autoId : override
  const toggle = (id) => setOverride(openId === id ? null : id)

  const isDone = (id) => steps.find(s => s.id === id)?.done
  const stepProps = (id, i) => ({
    index: i, total: 5,
    done: isDone(id), active: !complete && steps[currentIndex]?.id === id,
    open: openId === id, onToggle: () => toggle(id),
  })

  // Image and weights come from backend config (GET /sites/agent-install) so
  // republishing the model is one change in one place. MODEL_URL / MODEL_SHA256
  // are not decoration: with DETECTOR_MODE=yolo and an empty models volume the
  // agent exits at startup rather than run blind (edge/model.py), so a config
  // generated without them hands the customer a crash-looping container.
  const envFile = [
    `FIREMEX_CLOUD_URL=${CLOUD_URL}`,
    `AGENT_TOKEN=<paste your site token here>`,
    `DETECTOR_MODE=yolo`,
    `MODEL_PATH=/app/models/fire_model.pt`,
    ...(install?.model_url    ? [`MODEL_URL=${install.model_url}`]       : []),
    ...(install?.model_sha256 ? [`MODEL_SHA256=${install.model_sha256}`] : []),
  ].join('\n')

  const composeFile = `services:
  agent:
    image: ${install?.agent_image || 'ghcr.io/malika1234m/firemex-agent:latest'}
    restart: unless-stopped
    env_file: ./edge.env
    volumes: [agent_models:/app/models]
volumes:
  agent_models:`

  return (
    // Two columns from xl up; below that the rail drops away entirely rather
    // than squeezing the steps, since the guide is the thing that must stay
    // readable on a laptop.
    <div className="fade-up flex gap-6 items-start">
      <div className="flex-1 min-w-0 max-w-3xl space-y-5">
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
        the edge agent — watches your cameras on your network and sends only detections and a thumbnail
        here. Live video leaves your site only while you're watching a camera, and is never stored.
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
          <p>
            On any always-on computer at your site with Docker installed, download both files into
            one folder. Nothing else needs installing — no Python, no code to clone.
          </p>
          {install && !install.model_configured && (
            <div className="flex items-start gap-2.5 rounded-lg border border-hazard/30 bg-hazard/[0.06] p-3">
              <AlertTriangle size={14} className="text-hazard shrink-0 mt-0.5" />
              <p className="text-[11.5px] text-slate-400 leading-relaxed">
                No detection weights are published for this deployment yet, so the file below has no{' '}
                <code className="font-mono text-slate-300">MODEL_URL</code> and the agent will stop at
                startup rather than run without a model. Set{' '}
                <code className="font-mono text-slate-300">AGENT_MODEL_URL</code> on the server, or run
                with <code className="font-mono text-slate-300">DETECTOR_MODE=mock</code> to test the
                connection only.
              </p>
            </div>
          )}
          <Snippet label="1. Configuration" filename="edge.env" code={envFile} />
          <p className="text-slate-600 -mt-1">
            Replace <code className="font-mono text-slate-400">&lt;paste your site token here&gt;</code> with
            the enrollment token from step 2, then save.
          </p>
          <Snippet label="2. Docker setup" filename="docker-compose.yml" code={composeFile} />
          <Snippet label="3. In that folder, check the connection then start it" code={`docker compose run --rm agent python agent.py --selftest\ndocker compose up -d`} />
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

      <SidePanel
        counts={counts}
        agentOnline={Boolean(steps.find(s => s.id === 'agent')?.done)}
        haLinked={haLinked}
      />
    </div>
  )
}
