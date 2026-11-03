import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { useAuth } from './AuthContext'

/**
 * The signed-in user's organization: its plan and how far first-time setup
 * got.
 *
 * A context and not a plain hook because several components read it at once —
 * the route guard, the sidebar and the setup pages. With per-component state,
 * saving a setup step updated only the copy owned by the page it was saved
 * on, and the route guard kept sending the admin back to a step already done.
 * One shared copy means one update reaches every reader.
 */
export const DEPLOYMENT_MODES = {
  HOME_ASSISTANT: 'home_assistant',
  EDGE: 'edge',
  UNSET: 'unset',
}

const OrganizationContext = createContext(null)

export function OrganizationProvider({ children }) {
  const { user } = useAuth()
  const [org, setOrg] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    // Signed out there is no organization to fetch, and the landing page is
    // public — asking anyway would just 401 on every visit.
    if (!user) {
      setOrg(null)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const r = await apiFetch('/organizations/me')
      setOrg(r.ok ? await r.json() : null)
    } catch {
      setOrg(null)
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => { load() }, [load])

  const value = {
    org,
    loading,
    mode: org?.deployment_mode ?? DEPLOYMENT_MODES.UNSET,
    // A brand-new account that has never opened first-time setup. Accounts
    // from before the setup existed already chose how they run, so they are
    // not sent through it again.
    needsOnboarding: !loading && Boolean(org) && !org.onboarding_completed
      && !org.onboarding_step && org.deployment_mode === DEPLOYMENT_MODES.UNSET,
    refresh: load,
    setOrg,
  }

  return <OrganizationContext.Provider value={value}>{children}</OrganizationContext.Provider>
}

export function useOrganization() {
  const ctx = useContext(OrganizationContext)
  if (!ctx) throw new Error('useOrganization must be used within OrganizationProvider')
  return ctx
}
