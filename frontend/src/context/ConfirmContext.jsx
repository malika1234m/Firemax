import { createContext, useContext, useState, useCallback, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'

const ConfirmContext = createContext(null)

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null)
  const resolver = useRef(null)

  const confirm = useCallback((opts) => {
    setState(opts)
    return new Promise(resolve => { resolver.current = resolve })
  }, [])

  const handle = (result) => {
    setState(null)
    resolver.current?.(result)
  }

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {state && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="glass-card border border-white/[0.1] rounded-xl p-5 w-full max-w-sm space-y-4 fade-up">
            <div className="flex items-start gap-3">
              <div className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0
                ${state.danger ? 'bg-hazard/15 text-hazard' : 'bg-brand/15 text-brand'}`}>
                <AlertTriangle size={16} />
              </div>
              <div>
                <p className="font-raj font-semibold text-[14px] text-white">{state.title}</p>
                {state.message && <p className="text-[12px] text-slate-500 mt-1">{state.message}</p>}
              </div>
            </div>
            <div className="flex items-center gap-3 justify-end pt-1">
              <button onClick={() => handle(false)}
                      className="text-sm text-slate-400 hover:text-slate-200 px-4 py-2 transition-colors">
                Cancel
              </button>
              <button onClick={() => handle(true)}
                      className={`text-sm font-medium px-4 py-2 rounded-lg transition-colors
                        ${state.danger ? 'bg-hazard text-white hover:bg-hazard/85' : 'bg-brand text-void hover:bg-brand/85'}`}>
                {state.confirmLabel ?? 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used within ConfirmProvider')
  return ctx.confirm
}
