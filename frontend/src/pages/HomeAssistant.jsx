import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Home, RefreshCw, CheckCircle2, AlertCircle, Monitor, X, Wrench, Sparkles, ExternalLink, Info,
} from 'lucide-react'
import { apiJson } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { useConnection } from '../hooks/useConnection'
import PageHeader from '../components/PageHeader'
import InstallSteps from '../components/InstallSteps'
import { CHANGELOG_URL, DOCS_URL, STATUS_STYLE, WHATS_NEW, timeAgo } from '../lib/homeAssistant'

function Section({ id, title, icon: Icon, children, action }) {
  return (
    <section id={id} className="glass-card border border-white/[0.07] rounded-xl p-6 scroll-mt-6">
      <div className="flex items-center justify-between gap-3 mb-5">
        <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100">
          <Icon size={14} className="text-slate-500" /> {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  )
}

export default function HomeAssistant() {
  const { isAdmin } = useAuth()
  const { toast } = useToast()
  const confirm = useConfirm()
  const { licence, installs, status, allowed, checking, reload } = useConnection()
  const { hash } = useLocation()

  // The Overview links straight to the reconnection help.
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' })
  }, [hash])

  // An entry the owner does not recognise means the token was shared:
  // removing it frees the seat and stops that machine taking it back.
  const remove = async (install) => {
    if (!await confirm({
      title: 'Remove this installation?',
      message: 'That Home Assistant drops to the one-camera free tier the next time it checks its '
             + 'token, and cannot use this token again.',
      danger: true,
      confirmLabel: 'Remove',
    })) return
    try {
      await apiJson(`/licence/me/activations/${install.install_id}`, { method: 'DELETE' })
      toast({ type: 'success', message: 'Installation removed.' })
      reload()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not remove the installation' })
    }
  }

  return (
    <div className="max-w-4xl space-y-6 fade-up">
      <PageHeader title="Home Assistant Connection"
                  subtitle="Your cameras and fire detection live in Home Assistant. Here you can check it's talking to your account." />

      <Section title="Connection status" icon={Home}
               action={allowed && (
                 <button onClick={reload} disabled={checking}
                         className="inline-flex items-center gap-1.5 text-[12px] text-slate-400 hover:text-slate-200 border border-white/[0.1] rounded-lg px-3 py-1.5 disabled:opacity-40 transition-colors">
                   <RefreshCw size={12} className={checking ? 'animate-spin' : ''} /> Check again
                 </button>
               )}>
        {!allowed ? (
          <p className="text-[13px] text-slate-500">An admin on your account can see these details — ask them if you need anything here.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <span className={`inline-flex items-center gap-1.5 text-[13px] font-medium px-3 py-1.5 rounded-lg border ${STATUS_STYLE[status.state]}`}>
                {status.state === 'connected' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                {status.label ?? 'Checking…'}
              </span>
              {status.lastSeen && (
                <span className="text-[12.5px] text-slate-500">
                  Last successful communication {timeAgo(status.lastSeen)} · add-on {status.version || '?'}
                </span>
              )}
            </div>
            <p className="text-[12px] text-slate-600 mt-3">
              The add-on checks its access token when it starts and once a day while it runs. That
              check is the only thing it sends us — no video, no pictures, no detections.
            </p>

            <h3 className="text-[12px] font-semibold text-slate-400 mt-6 mb-2">
              Installations using your token ({status.count ?? 0} of {licence?.max_installs ?? '—'})
            </h3>
            {installs === null ? (
              <p className="text-[12px] text-slate-600">Loading…</p>
            ) : installs.length === 0 ? (
              <p className="text-[12px] text-slate-600">Nothing here yet. Your Home Assistant shows up the first time the add-on checks your token — usually a minute after you press Start.</p>
            ) : (
              <ul className="space-y-1.5">
                {installs.map(i => (
                  <li key={i.install_id}
                      className="flex items-center gap-3 bg-black/30 border border-white/[0.06] rounded-lg px-3 py-2">
                    <Monitor size={13} className="text-slate-500 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="font-mono text-[11.5px] text-slate-300 truncate">{i.install_id}</p>
                      <p className="text-[11px] text-slate-600">
                        Add-on {i.addon_version || '?'} · connected {new Date(i.first_seen).toLocaleDateString()} · last seen {timeAgo(i.last_seen)}
                      </p>
                    </div>
                    {isAdmin && (
                      <button type="button" onClick={() => remove(i)}
                              className="inline-flex items-center gap-1 text-[11.5px] text-slate-400 hover:text-red-300 border border-white/[0.09] rounded-md px-2 py-1 transition-colors">
                        <X size={11} /> Remove
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Section>

      <Section title="Set up the FiremeX add-on" icon={Sparkles}>
        <p className="text-[12.5px] text-slate-500 mb-5 flex items-start gap-2">
          <Info size={13} className="shrink-0 mt-0.5" />
          <span>Needs Home Assistant OS or Supervised — Home Assistant Container has no add-on store.</span>
        </p>
        <InstallSteps token={allowed ? (licence?.licence_key ?? '') : undefined} />
      </Section>

      <Section id="reconnect" title="Not connected, or stopped checking in?" icon={Wrench}>
        <ul className="space-y-3 text-[13px] text-slate-400 leading-relaxed">
          <li><span className="text-slate-200">Is the add-on running?</span> In Home Assistant open the FiremeX add-on and press Start (or Restart). Turn on <span className="text-slate-300">Start on boot</span> so it comes back after a power cut.</li>
          <li><span className="text-slate-200">Is the token right?</span> Copy it again from{' '}
            <Link to="/tokens" className="text-brand hover:underline">Access Tokens</Link>, paste it into <span className="font-mono text-slate-300">licence_key</span>, Save, and restart. After generating a new token, every Home Assistant needs the new one.</li>
          <li><span className="text-slate-200">Too many installations?</span> The add-on log says "already active on … installation(s)". Remove the old one above — for example after reinstalling Home Assistant.</li>
          <li><span className="text-slate-200">No internet?</span> Detection keeps working offline for up to 60 days; the status here updates when Home Assistant is back online.</li>
          <li><span className="text-slate-200">Still stuck?</span> The add-on's <span className="text-slate-300">Log</span> tab explains every licence check.{' '}
            <Link to="/support" className="text-brand hover:underline">Contact support</Link> with what it says.</li>
        </ul>
      </Section>

      <Section title="What's new in the add-on" icon={Sparkles}
               action={<a href={CHANGELOG_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12px] text-brand hover:underline">Full changelog <ExternalLink size={11} /></a>}>
        <div className="space-y-4">
          {WHATS_NEW.map(r => (
            <div key={r.version}>
              <p className="text-[12.5px] font-semibold text-slate-200">Version {r.version}</p>
              <ul className="mt-1.5 space-y-1 text-[12.5px] text-slate-400">
                {r.items.map(t => <li key={t}>• {t}</li>)}
              </ul>
            </div>
          ))}
        </div>
        <p className="text-[12px] text-slate-600 mt-5">
          Home Assistant shows an <span className="text-slate-400">Update</span> button on the add-on when a new version is out.{' '}
          <a href={DOCS_URL} target="_blank" rel="noreferrer" className="text-brand hover:underline">Add-on documentation</a>
        </p>
      </Section>
    </div>
  )
}
