import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Home, Server, Check, ArrowRight, Loader2, Info } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { useOrganization, DEPLOYMENT_MODES } from '../context/OrganizationContext'
import { useToast } from '../context/ToastContext'

/**
 * The question every new customer has to answer before any of the setup guide
 * makes sense: where is detection going to run?
 *
 * FiremeX is primarily a Home Assistant add-on. Most customers already have
 * Home Assistant watching their building, and in that case FiremeX installs
 * into it in three clicks — no account on a box, no token to copy, no camera
 * credentials entered a second time.
 *
 * The standalone edge agent still exists for sites with no Home Assistant, or
 * where one dashboard has to cover several buildings. The detection model is
 * identical; what differs is what the customer installs and where the alerts
 * are reviewed. Those two journeys share almost no steps, which is exactly why
 * we ask rather than showing a combined guide nobody can follow.
 */

const OPTIONS = [
  {
    mode: DEPLOYMENT_MODES.HOME_ASSISTANT,
    icon: Home,
    badge: 'Recommended',
    title: 'Home Assistant add-on',
    tagline: 'You already run Home Assistant',
    blurb:
      'FiremeX installs into Home Assistant and reads the cameras it already has. ' +
      'Detection runs on that machine — video never leaves your network.',
    points: [
      'Install from the Add-on Store, press Start',
      'Uses your existing camera integrations',
      'Alerts and incidents live in Home Assistant',
      'No account on the box, no token to copy',
      'Works with no internet after setup',
    ],
    requires: 'Requires Home Assistant OS or Supervised (Container has no add-ons).',
    accent: 'text-live',
    ring: 'hover:border-live/40',
    dot: 'bg-live',
  },
  {
    mode: DEPLOYMENT_MODES.EDGE,
    icon: Server,
    badge: null,
    title: 'FiremeX edge agent',
    tagline: 'No Home Assistant, or several sites',
    blurb:
      'A small agent runs on a machine at your site, connects to your cameras directly, ' +
      'and reports to this dashboard. Detection still runs on your hardware.',
    points: [
      'Runs anywhere Docker runs',
      'Connects straight to RTSP cameras',
      'One dashboard across several buildings',
      'Incident history, users and shifts in the cloud',
      'Home Assistant optional, for automations',
    ],
    requires: 'Requires a machine that stays on, on the same network as the cameras.',
    accent: 'text-brand',
    ring: 'hover:border-brand/40',
    dot: 'bg-brand',
  },
]

function OptionCard({ option, busy, onChoose }) {
  const Icon = option.icon
  return (
    <div
      className={`glass-card border border-white/[0.07] rounded-xl p-6 flex flex-col
                  transition-colors ${option.ring}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="w-11 h-11 rounded-lg bg-white/[0.04] border border-white/[0.06]
                        flex items-center justify-center shrink-0">
          <Icon size={20} className={option.accent} />
        </div>
        {option.badge && (
          <span className="text-[10px] font-semibold tracking-wider uppercase
                           px-2 py-1 rounded-full bg-live/10 text-live border border-live/30">
            {option.badge}
          </span>
        )}
      </div>

      <h3 className="font-raj font-bold text-xl text-white mt-4">{option.title}</h3>
      <p className={`text-xs font-medium mt-1 ${option.accent}`}>{option.tagline}</p>
      <p className="text-sm text-slate-400 mt-3 leading-relaxed">{option.blurb}</p>

      <ul className="mt-5 space-y-2 flex-1">
        {option.points.map(p => (
          <li key={p} className="flex items-start gap-2.5 text-sm text-slate-300">
            <Check size={15} className={`${option.accent} mt-0.5 shrink-0`} />
            <span>{p}</span>
          </li>
        ))}
      </ul>

      <p className="mt-5 text-xs text-slate-500 flex items-start gap-2">
        <Info size={13} className="mt-0.5 shrink-0" />
        <span>{option.requires}</span>
      </p>

      <button
        onClick={() => onChoose(option.mode)}
        disabled={Boolean(busy)}
        className="mt-6 w-full h-11 rounded-lg bg-brand hover:bg-ember-dark disabled:opacity-50
                   text-white font-semibold text-sm flex items-center justify-center gap-2
                   transition-colors"
      >
        {busy === option.mode
          ? <><Loader2 size={16} className="animate-spin" /> Setting up…</>
          : <>Set up this way <ArrowRight size={16} /></>}
      </button>
    </div>
  )
}

export default function ChooseSetup() {
  const { chooseMode } = useOrganization()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [busy, setBusy] = useState(null)

  const choose = async (mode) => {
    setBusy(mode)
    try {
      await chooseMode(mode)
      navigate(mode === DEPLOYMENT_MODES.HOME_ASSISTANT
        ? '/get-started/home-assistant'
        : '/get-started')
    } catch (err) {
      toast({ type: 'error', message: err?.message || 'Could not save your choice — please try again.' })
      setBusy(null)
    }
  }

  return (
    <div className="max-w-5xl">
      <PageHeader
        title="How do you want to run FiremeX?"
        subtitle="The detection model is the same either way — this only decides what you install and where you review alerts."
      />

      <div className="grid md:grid-cols-2 gap-5 mt-2">
        {OPTIONS.map(o => (
          <OptionCard key={o.mode} option={o} busy={busy} onChoose={choose} />
        ))}
      </div>

      <p className="text-xs text-slate-500 mt-6">
        You can change this later in <span className="text-slate-400">Settings → Organization</span>.
        Nothing is locked in — it only decides which guide you see.
      </p>
    </div>
  )
}
