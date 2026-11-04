import { Check, Loader2, Minus, Plus } from 'lucide-react'

const ORDER = ['free', 'starter', 'pro']

/** "$9", "$4.50" — whole dollars without decimals. */
export function money(n) {
  return `$${Number.isInteger(n) ? n : n.toFixed(2)}`
}

/** What a plan costs for an interval and camera count, as a number. */
export function planPrice(plan, interval, cameras) {
  const unit = interval === 'year' ? plan.price_year_usd : plan.price_month_usd
  return plan.per_camera ? unit * cameras : unit
}

export function IntervalToggle({ interval, onChange }) {
  return (
    <div role="radiogroup" aria-label="Billing period"
         className="inline-flex items-center rounded-lg border border-white/[0.1] bg-white/[0.02] p-1">
      {[['month', 'Monthly'], ['year', 'Yearly']].map(([id, label]) => (
        <button key={id} type="button" role="radio" aria-checked={interval === id} onClick={() => onChange(id)}
                className={`h-9 px-4 rounded-md text-[13px] font-medium transition-colors
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60
                  ${interval === id ? 'bg-white/[0.08] text-white' : 'text-slate-400 hover:text-slate-200'}`}>
          {label}
          {id === 'year' && <span className="ml-2 text-[11px] text-safe font-semibold">2 months free</span>}
        </button>
      ))}
    </div>
  )
}

export function CameraStepper({ value, min, max, onChange }) {
  const set = (v) => onChange(Math.max(min, Math.min(max, v)))
  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={() => set(value - 1)} disabled={value <= min} aria-label="Fewer cameras"
              className="w-9 h-9 rounded-lg border border-white/[0.12] flex items-center justify-center text-slate-300 hover:bg-white/[0.05] disabled:opacity-30">
        <Minus size={14} />
      </button>
      <input type="number" min={min} max={max} value={value} aria-label="Cameras"
             onChange={e => set(Number(e.target.value) || min)}
             className="w-16 h-9 rounded-lg bg-black/30 border border-white/[0.1] text-center font-mono text-[14px] text-white outline-none focus:border-brand/50" />
      <button type="button" onClick={() => set(value + 1)} disabled={value >= max} aria-label="More cameras"
              className="w-9 h-9 rounded-lg border border-white/[0.12] flex items-center justify-center text-slate-300 hover:bg-white/[0.05] disabled:opacity-30">
        <Plus size={14} />
      </button>
    </div>
  )
}

/**
 * Free / Home / Pro cards. The caller decides what choosing does (checkout,
 * changing a running subscription, or cancelling down to Free) through
 * `onChoose(planId)`, and what each button says through `actionFor(plan)`,
 * which returns { label, kind: 'primary'|'secondary'|'current'|'none', disabled }.
 */
export default function PlanPicker({ plans, interval, cameras, onCameras, actionFor, onChoose, busy }) {
  return (
    <div className="grid md:grid-cols-3 gap-4">
      {ORDER.filter(id => plans[id]).map(id => {
        const p = plans[id]
        const action = actionFor(p)
        const price = planPrice(p, interval, cameras)
        const highlighted = action.kind === 'current'
        return (
          <div key={id} className={`relative rounded-xl border p-5 flex flex-col
            ${highlighted ? 'border-brand/50 bg-brand/[0.06]' : 'border-white/[0.07] bg-panel/70'}`}>
            {highlighted && (
              <span className="absolute -top-2.5 left-5 text-[10.5px] font-semibold uppercase tracking-wider bg-brand text-white rounded px-2 py-0.5">
                Your plan
              </span>
            )}
            <p className="text-[13px] font-medium text-slate-300">{p.label}</p>
            <p className="font-raj font-bold text-[34px] text-white leading-none mt-2">
              {price ? money(price) : 'Free'}
              {price ? <span className="text-[12.5px] text-slate-400 font-sans font-normal"> / {interval}</span> : null}
            </p>
            <p className="text-[12.5px] text-slate-400 mt-2 min-h-[20px]">
              {p.per_camera
                ? `${money(interval === 'year' ? p.price_year_usd : p.price_month_usd)} per camera · ${p.min_cameras}–${p.max_cameras} cameras`
                : `${p.cameras} camera${p.cameras === 1 ? '' : 's'}${price && interval === 'year' ? ` · ${money(p.price_month_usd)}/month if monthly` : ''}`}
            </p>

            {p.per_camera && (
              <div className="mt-4 flex items-center justify-between gap-3 rounded-lg bg-black/20 border border-white/[0.06] px-3 py-2.5">
                <span className="text-[12.5px] text-slate-300">Cameras</span>
                <CameraStepper value={cameras} min={p.min_cameras} max={p.max_cameras} onChange={onCameras} />
              </div>
            )}

            <ul className="mt-4 pt-4 border-t border-white/[0.06] space-y-2 flex-1">
              {p.features.map(f => (
                <li key={f} className="flex items-start gap-2 text-[12.5px] text-slate-400 leading-snug">
                  <Check size={13} className="text-brand shrink-0 mt-0.5" strokeWidth={2.5} /> {f}
                </li>
              ))}
            </ul>

            <div className="mt-5">
              {action.kind === 'none' ? <div className="h-11" />
                : action.kind === 'current' ? (
                  <div className="h-11 flex items-center justify-center gap-1.5 text-[13px] text-brand font-medium rounded-lg bg-brand/10 border border-brand/20">
                    <Check size={14} /> {action.label || 'Current plan'}
                  </div>
                ) : (
                  <button type="button" onClick={() => onChoose(id)} disabled={action.disabled || busy === id}
                          className={`${action.kind === 'primary' ? 'btn-primary' : 'btn-secondary'} w-full`}>
                    {busy === id ? <><Loader2 size={14} className="animate-spin" /> Working…</> : action.label}
                  </button>
                )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
