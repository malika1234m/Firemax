import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Home, Store, SlidersHorizontal, Bell, ExternalLink, Info, ArrowLeftRight } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { Step, Snippet } from './GetStarted'

/**
 * Setup guide for the Home Assistant add-on — the primary way FiremeX is run.
 *
 * Deliberately shorter than the edge-agent guide, because the journey genuinely
 * is shorter: there is no site to create, no enrollment token to copy, and no
 * camera credentials to enter a second time. Home Assistant already holds the
 * cameras, and the add-on reads them.
 *
 * Nothing here is tracked as "done" the way the edge guide tracks a site coming
 * online. The cloud has no visibility into a fully-local install — that is the
 * point of it — so the guide tells the customer what to look for in their own
 * Home Assistant log instead of pretending to know.
 */

const REPO_URL = 'https://github.com/malika1234m/Firemax'

const HEALTHY_LOG = `FiremeX Home Assistant add-on v1.1.0 — fully local
model verified: /data/fire_model.pt
Detector: YOLO (real model)  alerting on: fire, smoke, flame
camera added: Warehouse Bay (camera.warehouse_bay)
watching 1 camera(s)`

export default function GetStartedHA() {
  const [open, setOpen] = useState('repo')
  const toggle = (id) => setOpen(open === id ? null : id)
  const props = (id, i) => ({
    index: i, total: 4, open: open === id, onToggle: () => toggle(id),
    done: false, active: open === id,
  })

  return (
    <div className="max-w-5xl">
      <PageHeader
        title="Get Started — Home Assistant"
        subtitle="Four steps. Detection runs inside Home Assistant on your own hardware."
      />

      <div className="glass-card border border-white/[0.07] rounded-xl p-5 mb-6 flex items-start gap-3">
        <Home size={18} className="text-live mt-0.5 shrink-0" />
        <div className="text-sm text-slate-300 leading-relaxed">
          <span className="font-semibold text-white">FiremeX runs inside Home Assistant.</span>{' '}
          It reads the cameras Home Assistant already has, runs the detection model on that
          machine, and writes alerts back as Home Assistant entities. Your video never leaves
          your network, and no FiremeX account is needed on the box.
          <div className="text-xs text-slate-500 mt-2">
            Requires Home Assistant <span className="text-slate-400">OS</span> or{' '}
            <span className="text-slate-400">Supervised</span>. Home Assistant Container has no
            Supervisor and therefore no add-ons —{' '}
            <Link to="/get-started" className="text-brand hover:underline">
              use the edge agent instead
            </Link>.
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <Step {...props('repo', 0)} icon={Store}
              title="Add the FiremeX repository"
              summary="Settings → Add-ons → Add-on Store → ⋮ → Repositories">
          <p className="text-sm text-slate-400 mb-3">
            In Home Assistant, go to <span className="text-slate-300">Settings → Add-ons →
            Add-on Store</span>, open the <span className="text-slate-300">⋮</span> menu in the
            top right, choose <span className="text-slate-300">Repositories</span>, and paste
            this URL.
          </p>
          <Snippet label="Add-on repository" code={REPO_URL} />
          <p className="text-xs text-slate-500 mt-3">
            FiremeX then appears in the store. You only ever do this once.
          </p>
        </Step>

        <Step {...props('install', 1)} icon={Home}
              title="Install FiremeX and press Start"
              summary="The add-on sets itself up on first run">
          <p className="text-sm text-slate-400">
            Find <span className="text-slate-300">FiremeX Fire &amp; Smoke Detection (Local)</span>{' '}
            in the store and click <span className="text-slate-300">Install</span>. The first
            start downloads the detection model and verifies its checksum, so give it a minute.
          </p>
          <p className="text-sm text-slate-400 mt-3">
            On start it creates your FiremeX dashboard, the operator controls and the automations
            for you — there is no script to run.
          </p>
          <div className="mt-4">
            <Snippet label="A healthy start looks like this in the add-on Log tab" code={HEALTHY_LOG} />
          </div>
        </Step>

        <Step {...props('tune', 2)} icon={SlidersHorizontal}
              title="Choose which cameras to watch"
              summary="Configuration tab — optional, defaults work">
          <p className="text-sm text-slate-400">
            By default FiremeX watches <span className="text-slate-300">every</span> camera entity
            Home Assistant has. On the <span className="text-slate-300">Configuration</span> tab you
            can name specific ones instead — worth doing, because running the model on a doorbell
            costs CPU and false alarms rather than safety.
          </p>
          <ul className="mt-3 space-y-2 text-sm text-slate-400">
            <li><span className="text-slate-300">cameras</span> — leave empty for all, or list entity ids</li>
            <li><span className="text-slate-300">confidence_threshold</span> — how sure the model must be</li>
            <li><span className="text-slate-300">process_fps</span> — how often each camera is analysed</li>
            <li><span className="text-slate-300">hazard_classes</span> — which hazards raise an alert</li>
          </ul>
          <p className="text-xs text-slate-500 mt-3 flex items-start gap-2">
            <Info size={13} className="mt-0.5 shrink-0" />
            <span>
              <span className="text-slate-400">hazard_classes</span> defaults to fire, smoke and
              flame. The colour and heat-shimmer detectors are included but off by default —
              Home Assistant re-encodes camera frames, and that compression noise makes them
              misfire. Turn them on once you have tested them against your own cameras.
            </span>
          </p>
        </Step>

        <Step {...props('review', 3)} icon={Bell}
              title="Review your first alert"
              summary="FiremeX raises alerts — you confirm them into incidents">
          <p className="text-sm text-slate-400">
            Open the <span className="text-slate-300">FiremeX</span> dashboard in your Home
            Assistant sidebar. When something is detected, the{' '}
            <span className="text-slate-300">Alerts</span> tab shows the annotated frame the model
            produced, next to a <span className="text-slate-300">Confirm</span> button for that
            camera.
          </p>
          <p className="text-sm text-slate-400 mt-3">
            Nothing happens to your building until you press it. Sprinklers, sirens and call-outs
            are wired to the incident, never to a detection — the model is confident and sometimes
            wrong, and a false sprinkler discharge is its own emergency.
          </p>
          <p className="text-sm text-slate-400 mt-3">
            The add-on ships with stand-in switches so you can see the workflow immediately.
            Swap them for your real devices in{' '}
            <span className="text-slate-300">Settings → Automations</span> when you are ready.
          </p>
        </Step>
      </div>

      <div className="glass-card border border-white/[0.07] rounded-xl p-5 mt-6">
        <div className="flex items-start gap-3">
          <ArrowLeftRight size={16} className="text-slate-500 mt-0.5 shrink-0" />
          <div className="text-sm text-slate-400">
            <span className="text-slate-300 font-medium">Several buildings, or no Home Assistant?</span>{' '}
            The edge agent reports to this dashboard instead, with incident history and users
            across every site.{' '}
            <Link to="/get-started" className="text-brand hover:underline inline-flex items-center gap-1">
              Edge agent guide <ExternalLink size={12} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
