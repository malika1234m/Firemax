import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'

/**
 * Shared onboarding state for the Get Started guide and the inline stepper that
 * appears on the pages where the work actually happens (Sites, etc).
 *
 * Progress is derived from real data — a camera row, a site row, a site
 * reporting online, an alert — never from a "dismissed the tutorial" flag. That
 * matters: a checklist that ticks itself because someone clicked Next tells you
 * nothing, whereas these four conditions are exactly the things that must be
 * true for the product to be working at all.
 *
 * Home Assistant is deliberately NOT part of the count. It is genuinely
 * optional, and including it would leave every customer who doesn't use it
 * permanently stuck at "4 of 5".
 */
export const SETUP_STEPS = [
  { id: 'camera', label: 'Add a camera',     short: 'Camera', to: '/cameras' },
  { id: 'site',   label: 'Create a site',    short: 'Site',   to: '/sites'   },
  { id: 'agent',  label: 'Run the edge agent', short: 'Agent', to: '/sites'  },
  { id: 'alert',  label: 'See your first alert', short: 'Alert', to: '/alerts' },
]

export function useSetupProgress({ pollMs = 15000 } = {}) {
  const [state, setState] = useState({
    loading: true, camera: false, site: false, agent: false, alert: false, ha: false,
  })

  const load = useCallback(async () => {
    const get = (path) => apiFetch(path).then(r => (r.ok ? r.json() : null)).catch(() => null)
    const [cameras, sites, alerts, ha] = await Promise.all([
      get('/cameras/'), get('/sites/'), get('/alerts/?limit=1'), get('/ha/config'),
    ])
    setState({
      loading: false,
      camera: Array.isArray(cameras) && cameras.length > 0,
      site:   Array.isArray(sites)   && sites.length   > 0,
      agent:  Array.isArray(sites)   && sites.some(s => s.status === 'online'),
      alert:  Array.isArray(alerts)  && alerts.length  > 0,
      ha:     Boolean(ha?.ha_url),
    })
  }, [])

  useEffect(() => {
    load()
    if (!pollMs) return
    const id = setInterval(load, pollMs)
    return () => clearInterval(id)
  }, [load, pollMs])

  const steps = SETUP_STEPS.map(s => ({ ...s, done: state[s.id] }))
  const doneCount = steps.filter(s => s.done).length

  // The step to work on next is the first unfinished one, not simply the one
  // after the last tick — someone can complete steps out of order (creating a
  // site before adding a camera is perfectly reasonable) and the guide should
  // point at whatever is genuinely still missing.
  const currentIndex = steps.findIndex(s => !s.done)

  return {
    loading: state.loading,
    steps,
    doneCount,
    total: steps.length,
    currentIndex,                       // -1 once everything is done
    complete: currentIndex === -1,
    haLinked: state.ha,
    refresh: load,
  }
}
