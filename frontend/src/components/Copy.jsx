import { useState } from 'react'
import { Check, Copy } from 'lucide-react'

export function CopyButton({ text, label = 'Copy', className }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
      aria-live="polite"
      className={className ?? "flex items-center gap-1.5 text-[11px] text-slate-400 border border-white/[0.1] rounded-lg h-9 px-3 bg-panel/80 backdrop-blur hover:bg-white/[0.06] transition-colors shrink-0"}
    >
      {copied ? <><Check size={12} className="text-safe" /> Copied</> : <><Copy size={12} /> {label}</>}
    </button>
  )
}

/** A value the customer copies into Home Assistant, with its copy button. */
export function Snippet({ label, code }) {
  return (
    <div className="space-y-1.5">
      {label && <p className="text-[11px] text-slate-500 font-medium">{label}</p>}
      <div className="relative">
        <pre className="font-mono text-[11.5px] leading-relaxed text-slate-300 bg-black/40 border border-white/[0.08] rounded-lg p-3 pr-24 overflow-x-auto whitespace-pre-wrap break-all">{code}</pre>
        <div className="absolute top-1.5 right-1.5">
          <CopyButton text={code} />
        </div>
      </div>
    </div>
  )
}
