import { useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound, Eye, EyeOff, RefreshCw, ShieldCheck, ExternalLink, CheckCircle2, AlertCircle } from 'lucide-react'
import { apiJson } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { useConnection } from '../hooks/useConnection'
import { CopyButton } from '../components/Copy'
import PageHeader from '../components/PageHeader'
import { OPEN_ADDON_URL } from '../lib/homeAssistant'
import { planLabel } from '../lib/format'

/**
 * The access token is the add-on's licence key: the one thing that ties a
 * Home Assistant to this account. One token per account; replacing it revokes
 * the old one everywhere at once.
 */
export default function AccessTokens() {
  const { toast } = useToast()
  const confirm = useConfirm()
  const { licence, setLicence, status, reload } = useConnection()
  const [shown, setShown] = useState(false)
  const [rotating, setRotating] = useState(false)

  const key = licence?.licence_key
  const masked = key ? `${key.slice(0, 4)}${'•'.repeat(20)}${key.slice(-4)}` : 'Loading…'

  // Self-service on purpose: the token is pasted into a config field, so it
  // ends up in a screenshot or a support thread sooner or later.
  const rotate = async () => {
    if (!await confirm({
      title: 'Generate a new access token?',
      message: 'The current token stops working straight away and every Home Assistant using it '
             + 'drops to the one-camera free tier until you paste the new token into its '
             + 'Configuration tab.',
      danger: true,
      confirmLabel: 'Generate new token',
    })) return
    setRotating(true)
    try {
      setLicence(await apiJson('/licence/me/rotate', { method: 'POST' }))
      setShown(true)
      toast({ type: 'success', message: 'New access token generated. Paste it into Home Assistant.' })
      reload()
    } catch (err) {
      toast({ type: 'error', message: err.message || 'Could not generate a new token' })
    } finally {
      setRotating(false)
    }
  }

  return (
    <div className="max-w-3xl space-y-6 fade-up">
      <PageHeader title="Access Tokens" subtitle="The key that tells your Home Assistant which FiremeX plan it's on." />

      <section className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100">
            <KeyRound size={14} className="text-slate-500" /> Your access token
          </h2>
          {licence && (licence.entitled ? (
            <span className="inline-flex items-center gap-1.5 text-[11.5px] font-medium px-2.5 py-1 rounded-lg border bg-safe/10 text-safe border-safe/25">
              <CheckCircle2 size={12} /> Active — up to {licence.max_cameras} camera{licence.max_cameras === 1 ? '' : 's'}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-[11.5px] font-medium px-2.5 py-1 rounded-lg border bg-warn/10 text-warn border-warn/25">
              <AlertCircle size={12} /> Free plan — 1 camera
            </span>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
          <code className="flex-1 min-w-0 font-mono text-[13px] text-slate-200 bg-black/40 border border-white/[0.08] rounded-lg px-3 py-2.5 break-all">
            {shown && key ? key : masked}
          </code>
          <div className="flex items-center gap-2 shrink-0">
            <button type="button" onClick={() => setShown(v => !v)} disabled={!key}
                    className="flex items-center gap-1.5 text-[11px] text-slate-400 border border-white/[0.1] rounded-lg px-2.5 py-1.5 hover:bg-white/[0.06] disabled:opacity-40 transition-colors">
              {shown ? <><EyeOff size={12} /> Hide</> : <><Eye size={12} /> Show</>}
            </button>
            {key && <CopyButton text={key} />}
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-3 text-[12.5px]">
          <div className="rounded-lg bg-black/20 border border-white/[0.05] px-3 py-2.5">
            <p className="text-slate-400">Used by</p>
            <p className="text-slate-200 mt-0.5">
              {status.count ?? 0} of {licence?.max_installs ?? '—'} Home Assistant
            </p>
          </div>
          <div className="rounded-lg bg-black/20 border border-white/[0.05] px-3 py-2.5">
            <p className="text-slate-400">Plan</p>
            <p className="text-slate-200 mt-0.5">{licence ? `${planLabel(licence.plan)} · ${licence.max_cameras} camera${licence.max_cameras === 1 ? '' : 's'}` : '—'}</p>
          </div>
        </div>

        {!licence?.entitled && licence && (
          <p className="text-[12px] text-slate-400">
            You're on the Free plan, so this token lets FiremeX watch one camera.{' '}
            <Link to="/billing" className="text-brand hover:underline">Choose a plan</Link> to watch more.
          </p>
        )}

        <div className="pt-4 border-t border-white/[0.06] flex flex-wrap items-center gap-3">
          <button type="button" onClick={rotate} disabled={rotating || !licence}
                  className="inline-flex items-center gap-2 text-[12.5px] text-slate-300 hover:text-white border border-white/[0.12] rounded-lg px-3.5 py-2 disabled:opacity-40 transition-colors">
            <RefreshCw size={13} className={rotating ? 'animate-spin' : ''} />
            {rotating ? 'Generating…' : 'Generate new token'}
          </button>
          <p className="text-[11.5px] text-slate-600 flex-1 min-w-[220px]">
            Do this if the token was shared or shown somewhere it should not be. The old token is revoked at once.
          </p>
        </div>
      </section>

      <section className="glass-card border border-white/[0.07] rounded-xl p-6 space-y-3">
        <h2 className="text-[14.5px] font-semibold text-slate-100">Where it goes</h2>
        <p className="text-[13px] text-slate-400 leading-relaxed">
          In Home Assistant, open the FiremeX add-on, go to the <span className="text-slate-200">Configuration</span> tab,
          paste the token into <span className="font-mono text-slate-200">licence_key</span>, press{' '}
          <span className="text-slate-200">Save</span> and restart the add-on.
        </p>
        <a href={OPEN_ADDON_URL} target="_blank" rel="noreferrer"
           className="inline-flex items-center gap-1.5 text-[12.5px] text-brand hover:underline">
          Open FiremeX in Home Assistant <ExternalLink size={12} />
        </a>
      </section>

      <section className="glass-card border border-white/[0.07] rounded-xl p-6">
        <h2 className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-100 mb-3">
          <ShieldCheck size={14} className="text-slate-500" /> Keeping it safe
        </h2>
        <ul className="space-y-2 text-[12.5px] text-slate-400">
          <li>• Treat it like a password. Your plan covers one Home Assistant: if someone else uses the token, one of you is refused, and you'll see it in your account activity.</li>
          <li>• Copying the add-on to a second machine doesn't share the licence either — the copy is spotted and refused.</li>
          <li>• Each Home Assistant using it takes one of your plan's installations. You can see and remove them under{' '}
            <Link to="/home-assistant" className="text-brand hover:underline">Home Assistant Connection</Link>.</li>
          <li>• The add-on keeps your plan's cameras for 30 days without internet, then watches 1 camera until it can check in again.</li>
        </ul>
      </section>
    </div>
  )
}
