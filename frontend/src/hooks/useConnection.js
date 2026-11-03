import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { connectionStatus } from '../lib/homeAssistant'

/**
 * The org's access token and the Home Assistant installations using it.
 *
 * Both endpoints are admin-only; for an operator `allowed` is false and the
 * page says to ask an admin instead of showing empty data as if it were real.
 * `pollMs` keeps re-checking — used while the customer is in Home Assistant
 * pasting the token, so the page turns green by itself when the add-on checks in.
 */
export function useConnection({ pollMs } = {}) {
  const [licence, setLicence] = useState(null)
  const [installs, setInstalls] = useState(null)
  const [allowed, setAllowed] = useState(true)
  const [checking, setChecking] = useState(false)

  const reload = useCallback(async () => {
    setChecking(true)
    try {
      const [k, a] = await Promise.all([apiFetch('/licence/me'), apiFetch('/licence/me/activations')])
      if (k.status === 403 || a.status === 403) { setAllowed(false); return }
      if (k.ok) setLicence(await k.json())
      setInstalls(a.ok ? await a.json() : [])
    } catch {
      setInstalls(prev => prev ?? [])
    } finally {
      setChecking(false)
    }
  }, [])

  useEffect(() => { reload() }, [reload])
  useEffect(() => {
    if (!pollMs) return undefined
    const t = setInterval(reload, pollMs)
    return () => clearInterval(t)
  }, [pollMs, reload])

  return { licence, setLicence, installs, status: connectionStatus(installs), allowed, checking, reload }
}
