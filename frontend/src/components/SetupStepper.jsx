import { Link } from 'react-router-dom'
import { Check, ArrowRight } from 'lucide-react'
import { useSetupProgress } from '../hooks/useSetupProgress'

/**
 * Compact horizontal stepper shown at the top of the pages where setup work
 * actually happens, so someone mid-task can see where they are without going
 * back to the guide.
 *
 * It removes itself once setup is complete. A permanent checklist on a page a
 * customer uses every day stops being guidance and becomes clutter.
 */
export default function SetupStepper({ highlight }) {
  const { steps, doneCount, total, currentIndex, complete, loading } = useSetupProgress()

  if (loading || complete) return null

  // The caller can pin the "you are here" marker to the page the user is on
  // (Sites → the site step), which is more truthful than the global next-step
  // when they have jumped around.
  const activeIndex = highlight
    ? Math.max(steps.findIndex(s => s.id === highlight), 0)
    : currentIndex

  return (
    <div className="glass-card border border-white/[0.09] rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[12px] text-slate-300 font-medium">
          Setup <span className="text-slate-600">· {doneCount} of {total} done</span>
        </p>
        <Link to="/get-started"
              className="flex items-center gap-1.5 text-[11.5px] text-brand hover:underline shrink-0">
          Open guide <ArrowRight size={12} />
        </Link>
      </div>

      <ol className="flex items-stretch gap-1 overflow-x-auto pb-0.5">
        {steps.map((s, i) => {
          const active = i === activeIndex
          return (
            <li key={s.id} className="flex items-center gap-1 shrink-0">
              <Link
                to={s.to}
                className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 border transition-colors
                  ${s.done   ? 'border-safe/25  bg-safe/[0.06]  hover:bg-safe/[0.1]'
                  : active   ? 'border-brand/40 bg-brand/[0.1]   hover:bg-brand/[0.16]'
                             : 'border-white/[0.07] hover:bg-white/[0.03]'}`}
              >
                <span className={`w-[18px] h-[18px] shrink-0 rounded-full flex items-center justify-center text-[10px] font-semibold
                  ${s.done ? 'bg-safe/20 text-safe' : active ? 'bg-brand/25 text-brand' : 'bg-white/[0.06] text-slate-500'}`}>
                  {s.done ? <Check size={11} strokeWidth={3} /> : i + 1}
                </span>
                <span className={`text-[11.5px] whitespace-nowrap
                  ${s.done ? 'text-slate-500' : active ? 'text-brand font-medium' : 'text-slate-500'}`}>
                  {s.short}
                </span>
              </Link>
              {i < steps.length - 1 && (
                <span className={`w-4 h-px shrink-0 ${s.done ? 'bg-safe/30' : 'bg-white/[0.08]'}`} />
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
