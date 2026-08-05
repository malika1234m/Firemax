import { createContext, useContext, useCallback, useState } from 'react'
import { CheckCircle2, XCircle, Info, X } from 'lucide-react'

const ToastContext = createContext(null)
let idCounter = 0

const ICONS = { success: CheckCircle2, error: XCircle, info: Info }
const STYLES = {
  success: 'border-safe/30 text-safe',
  error:   'border-hazard/30 text-hazard',
  info:    'border-brand/30 text-brand',
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts(t => t.filter(x => x.id !== id))
  }, [])

  const toast = useCallback(({ type = 'info', message }) => {
    const id = ++idCounter
    setToasts(t => [...t, { id, type, message }])
    setTimeout(() => dismiss(id), 4500)
  }, [dismiss])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] space-y-2 w-full max-w-sm pointer-events-none">
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast, onDismiss }) {
  const Icon = ICONS[toast.type] ?? Info
  return (
    <div className={`glass-card border rounded-lg px-4 py-3 flex items-start gap-2.5 shadow-lg fade-up pointer-events-auto ${STYLES[toast.type]}`}>
      <Icon size={15} className="shrink-0 mt-0.5" />
      <p className="text-[12px] text-slate-200 flex-1">{toast.message}</p>
      <button onClick={onDismiss} className="text-slate-600 hover:text-slate-300 shrink-0">
        <X size={13} />
      </button>
    </div>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
