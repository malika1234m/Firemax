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
    counts: { cameras: 0, sites: 0, sitesOnline: 0, alerts: 0, alertsCapped: false },
  })

  // Alerts are fetched as a page, not a count — there is no count endpoint. The
  // cap is surfaced (alertsCapped) so the UI can render "50+" instead of
  // claiming a precise number it doesn't have.
  const ALERT_PAGE = 50

  const load = useCallback(async () => {
    const get = (path) => apiFetch(path).then(r => (r.ok ? r.json() : null)).catch(() => null)
    const [cameras, sites, alerts, ha] = await Promise.all([
      get('/cameras/'), get('/sites/'), get(`/alerts/?limit=${ALERT_PAGE}`), get('/ha/config'),
    ])
    const cameraList = Array.isArray(cameras) ? cameras : []
    const siteList   = Array.isArray(sites)   ? sites   : []
    const alertList  = Array.isArray(alerts)  ? alerts  : []
    const online     = siteList.filter(s => s.status === 'online')

    setState({
      loading: false,
      camera: cameraList.length > 0,
      site:   siteList.length   > 0,
      agent:  online.length     > 0,
      alert:  alertList.length  > 0,
      ha:     Boolean(ha?.ha_url),
      counts: {
        cameras: cameraList.length,
        sites: siteList.length,
        sitesOnline: online.length,
        alerts: alertList.length,
        alertsCapped: alertList.length >= ALERT_PAGE,
      },
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
    counts: state.counts,
    refresh: load,
  }
}
