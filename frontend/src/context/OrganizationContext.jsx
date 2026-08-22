import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { apiFetch, apiJson } from '../lib/api'
import { useAuth } from './AuthContext'

/**
 * The signed-in user's organization, and the deployment mode it has chosen.
 *
 * `deployment_mode` decides which setup guide a customer sees. The two paths —
 * the Home Assistant add-on and the standalone edge agent — share the detection
 * model and almost nothing else, so showing the wrong one wastes the customer's
 * time on steps that do not apply to them.
 *
 * It is read from the server rather than kept in local storage: the choice is
 * a property of the organization, so a second admin signing in on another
 * machine must see the same guide as the first.
 *
 * This is a context and not a plain hook because several components read the
 * mode at once — the route guard, the sidebar and the settings page. With
 * per-component state, answering the questionnaire updated only the copy owned
 * by the page you answered on; the route guard's copy still said "unanswered"
 * and bounced you straight back to the question, forever. One shared copy means
 * one update reaches every reader.
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

  const chooseMode = useCallback(async (mode) => {
    const updated = await apiJson('/organizations/me/deployment-mode', {
      method: 'PUT',
      body: JSON.stringify({ deployment_mode: mode }),
    })
    setOrg(updated)
    return updated
  }, [])

  const value = {
    org,
    loading,
    mode: org?.deployment_mode ?? DEPLOYMENT_MODES.UNSET,
    // A brand-new organization has not answered the questionnaire yet.
    needsSetupChoice: !loading && org?.deployment_mode === DEPLOYMENT_MODES.UNSET,
    isHomeAssistant: org?.deployment_mode === DEPLOYMENT_MODES.HOME_ASSISTANT,
    isEdge: org?.deployment_mode === DEPLOYMENT_MODES.EDGE,
    chooseMode,
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
