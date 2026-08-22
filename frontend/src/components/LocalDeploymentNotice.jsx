import { Home } from 'lucide-react'
import { useOrganization } from '../context/OrganizationContext'

/**
 * Explains why a cloud page is empty for a customer running the Home Assistant
 * add-on.
 *
 * The add-on is fully local — it talks only to Home Assistant and never to this
 * cloud, which is the whole point of it. The consequence is that Live Feed,
 * Incidents, Alerts and Cameras have nothing to show and never will, and the
 * ordinary empty states actively mislead: "No cameras yet — add your first
 * device" tells someone to do a thing that is both unnecessary and wrong, since
 * their cameras already exist inside Home Assistant.
 *
 * A screen that looks broken while working exactly as designed costs support
 * time and trust, so these pages say so plainly instead.
 *
 * Renders `children` — the page's normal empty state — for everyone else, so
 * wiring this in never changes what an edge-agent customer sees.
 */
export default function LocalDeploymentNotice({ what = 'This page', children = null }) {
  const { isHomeAssistant } = useOrganization()
  if (!isHomeAssistant) return children

  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <div className="w-11 h-11 rounded-full bg-live/10 border border-live/25 flex items-center justify-center">
        <Home size={18} className="text-live" />
      </div>
      <p className="text-slate-300 text-sm font-medium">
        FiremeX is running inside Home Assistant
      </p>
      <p className="text-slate-500 text-[12.5px] leading-relaxed max-w-md">
        {what} stays empty because your detections never leave your network. Open the{' '}
        <span className="text-slate-400">FiremeX</span> dashboard in your Home Assistant
        sidebar to see cameras, alerts and incidents.
      </p>
    </div>
  )
}
