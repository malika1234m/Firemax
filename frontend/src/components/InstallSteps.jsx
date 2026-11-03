import { ExternalLink, Store, KeyRound, Play, Info } from 'lucide-react'
import { Snippet } from './Copy'
import { ADD_REPO_URL, ADDON_NAME, OPEN_ADDON_URL, REPO_URL } from '../lib/homeAssistant'

function Num({ n }) {
  return (
    <span className="relative z-[1] w-7 h-7 rounded-full bg-void border border-brand/45 text-brand font-mono text-[12px] font-bold flex items-center justify-center shrink-0">
      {n}
    </span>
  )
}

/**
 * Installing the FiremeX add-on in Home Assistant, with the access token.
 *
 * Step 1 is a single button: my.home-assistant.io opens the customer's own
 * Home Assistant on the FiremeX add-on and, if the FiremeX repository is not
 * there yet, offers to add it with the address already filled in — nothing to
 * type. The manual route stays below it for Home Assistants that the link
 * cannot reach.
 */
export default function InstallSteps({ token }) {
  return (
    <ol>
      <li className="relative flex gap-4 pb-9 last:pb-0 before:absolute before:left-[13px] before:top-9 before:bottom-2 before:w-px before:bg-white/[0.08] last:before:hidden">
        <Num n={1} />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <p className="text-[15px] text-white font-medium">Open FiremeX in your Home Assistant</p>
            <p className="text-[13px] text-slate-400 mt-1.5 leading-relaxed">
              This opens the add-on store in your own Home Assistant. If the FiremeX repository
              is not added yet, Home Assistant asks to add it — the address is already typed in,
              so just press <span className="text-slate-300">Add</span>.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a href={OPEN_ADDON_URL} target="_blank" rel="noreferrer"
               className="btn-primary">
              <Store size={15} /> Open the add-on store <ExternalLink size={13} />
            </a>
            <a href={ADD_REPO_URL} target="_blank" rel="noreferrer"
               className="btn-secondary">
              Only add the repository <ExternalLink size={11} />
            </a>
          </div>
          <p className="text-[11.5px] text-slate-400 flex items-start gap-1.5">
            <Info size={12} className="shrink-0 mt-0.5" />
            <span>
              The first time, my.home-assistant.io asks for your Home Assistant address
              (for example <span className="font-mono text-slate-400">http://homeassistant.local:8123</span>)
              and remembers it.
            </span>
          </p>
          <details className="group">
            <summary className="text-[12px] text-slate-400 hover:text-slate-300 cursor-pointer select-none">
              Button not working? Add the repository by hand
            </summary>
            <div className="mt-3 space-y-3">
              <p className="text-[12px] text-slate-400 leading-relaxed">
                In Home Assistant open <span className="text-slate-300">Settings → Apps → Install app</span>{' '}
                (older versions: <span className="text-slate-300">Settings → Add-ons → Add-on Store</span>),
                press <span className="text-slate-300">⋮ → Repositories</span>, paste this address and press Add.
              </p>
              <Snippet label="Repository address" code={REPO_URL} />
            </div>
          </details>
        </div>
      </li>

      <li className="relative flex gap-4 pb-9 last:pb-0 before:absolute before:left-[13px] before:top-9 before:bottom-2 before:w-px before:bg-white/[0.08] last:before:hidden">
        <Num n={2} />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] text-white font-medium">Install it</p>
          <p className="text-[13px] text-slate-400 mt-1.5 leading-relaxed">
            Open <span className="text-slate-300">{ADDON_NAME}</span> and press{' '}
            <span className="text-slate-300">Install</span>. It takes a few minutes.
          </p>
        </div>
      </li>

      <li className="relative flex gap-4 pb-9 last:pb-0 before:absolute before:left-[13px] before:top-9 before:bottom-2 before:w-px before:bg-white/[0.08] last:before:hidden">
        <Num n={3} />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <p className="text-[15px] text-white font-medium flex items-center gap-2">
              <KeyRound size={14} className="text-slate-400" /> Paste your access token
            </p>
            <p className="text-[13px] text-slate-400 mt-1.5 leading-relaxed">
              On the add-on's <span className="text-slate-300">Configuration</span> tab, paste it into{' '}
              <span className="font-mono text-slate-300">licence_key</span> and press{' '}
              <span className="text-slate-300">Save</span>.
            </p>
          </div>
          {token !== undefined && (
            <Snippet label="Your access token" code={token || 'Loading…'} />
          )}
        </div>
      </li>

      <li className="relative flex gap-4 pb-9 last:pb-0 before:absolute before:left-[13px] before:top-9 before:bottom-2 before:w-px before:bg-white/[0.08] last:before:hidden">
        <Num n={4} />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] text-white font-medium flex items-center gap-2">
            <Play size={14} className="text-slate-400" /> Press Start
          </p>
          <p className="text-[13px] text-slate-400 mt-1.5 leading-relaxed">
            The add-on downloads the fire model, creates the FiremeX dashboard in your Home
            Assistant sidebar, and checks your token with us. This page shows it as connected
            within a minute.
          </p>
        </div>
      </li>
    </ol>
  )
}
