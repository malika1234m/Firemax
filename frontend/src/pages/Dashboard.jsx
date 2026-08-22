import { useEffect, useState } from 'react'
import { Camera, Bell, ShieldAlert, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { formatHazardLabel } from '../lib/format'
import PageHeader from '../components/PageHeader'
import LocalDeploymentNotice from '../components/LocalDeploymentNotice'
import { useOrganization } from '../context/OrganizationContext'

const RISK_STYLES = {
  Normal:   { cls: 'bg-safe/15 text-safe border-safe/25' },
  Elevated: { cls: 'bg-warn/15 text-warn border-warn/25' },
  Critical: { cls: 'bg-hazard/15 text-hazard border-hazard/25' },
}

export default function Dashboard() {
  const [cameras, setCameras] = useState([])
  const [alerts,  setAlerts]  = useState([])
  const [health,  setHealth]  = useState(null)
  const [time,    setTime]    = useState(new Date())

  useEffect(() => {
    const load = () => {
      apiFetch('/cameras/').then(r => r.json()).then(setCameras).catch(() => {})
      apiFetch('/alerts/?limit=20').then(r => r.json()).then(setAlerts).catch(() => {})
      // Real liveness from agent heartbeats. Counting `enabled` cameras here
      // told a customer with no agent running that every camera was reporting.
      apiFetch('/cameras/health').then(r => r.ok ? r.json() : null).then(setHealth).catch(() => {})
    }
    load()
    const id = setInterval(load, 15_000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const tick = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(tick)
  }, [])

  const online       = health ? health.online : 0
  const { isHomeAssistant } = useOrganization()
  const offlineCams  = cameras.filter(c => !health?.cameras?.[c.camera_id]?.online)
  const offlineCam   = offlineCams[0] ?? null

  // Distinguishes "an agent is running and a camera is down" from "nothing is
  // watching anything", which are very different situations for an operator.
  const anythingReporting = Boolean(health && health.online > 0)
  const cameraStatusText =
    // The add-on never reports here, so the cloud's view of "is anything
    // watching?" is meaningless for these customers — and the honest-looking
    // answer is the dangerous one: "detection is not running" is false, and an
    // operator who believes it thinks their building is unwatched.
    isHomeAssistant                 ? 'Detection runs inside Home Assistant'
    : cameras.length === 0          ? 'No cameras added yet'
    : !anythingReporting            ? 'No agent reporting — detection is not running'
    : offlineCams.length === 0      ? 'All cameras reporting'
    : offlineCams.length === 1      ? `1 camera not reporting — ${offlineCam.name}`
    :                                 `${offlineCams.length} cameras not reporting`
  const activeAlerts = alerts.filter(a => a.status !== 'resolved')
  const unacked      = activeAlerts.filter(a => !a.acknowledged)
  const zonesAffected = new Set(activeAlerts.map(a => a.zone)).size

  const riskLevel = activeAlerts.length === 0 ? 'Normal' : activeAlerts.length >= 3 ? 'Critical' : 'Elevated'
  const recent    = alerts.slice(0, 5)
  const preview   = alerts[0]

  return (
    <div className="relative space-y-6">
      {/* home-page style ambient ember glow */}
      <div aria-hidden className="pointer-events-none absolute -top-10 right-0 w-[26rem] h-[16rem] rounded-full bg-ember/[0.07] blur-[110px] -z-10" />

      <PageHeader title="Dashboard" subtitle="Real-time situation overview">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400 bg-white/[0.04] border border-white/[0.07] rounded-lg px-3 py-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-safe live-dot" /> LIVE {time.toLocaleTimeString('en-US', { hour12: false })}
          </span>
          <div className="relative w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.07] flex items-center justify-center">
            <Bell size={14} className="text-slate-400" />
            {unacked.length > 0 && <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-hazard border border-panel" />}
          </div>
        </div>
      </PageHeader>

      {/* ── Stat cards ─────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="glass-card rounded-xl p-4 border border-white/[0.07]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Cameras Online</span>
            <span className={`w-7 h-7 rounded-lg flex items-center justify-center border ${offlineCam ? 'bg-hazard/10 border-hazard/25' : 'bg-ember/10 border-ember/25'}`}>
              <Camera size={13} className={offlineCam ? 'text-hazard' : 'text-ember'} />
            </span>
          </div>
          <p className="font-raj font-bold text-[26px] leading-none text-white">
            {online}<span className="text-slate-600 text-lg font-medium">/{cameras.length}</span>
          </p>
          {/* Hazard-red is for "something is wrong". A Home Assistant install
              reporting nothing here is the normal, correct state, so it must
              not be coloured like a fault. */}
          <p className={`text-[11px] mt-2 ${isHomeAssistant || (cameras.length && !offlineCams.length)
                                              ? 'text-slate-600' : 'text-hazard'}`}>
            {cameraStatusText}
          </p>
        </div>

        <div className="glass-card rounded-xl p-4 border border-white/[0.07]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Current Risk Level</span>
            <span className={`w-7 h-7 rounded-lg flex items-center justify-center border ${riskLevel === 'Critical' ? 'bg-hazard/10 border-hazard/25' : 'bg-ember/10 border-ember/25'}`}>
              <ShieldAlert size={13} className={riskLevel === 'Critical' ? 'text-hazard' : 'text-ember'} />
            </span>
          </div>
          <span className={`inline-flex items-center gap-1.5 text-[13px] font-raj font-semibold px-2.5 py-1 rounded-md border ${RISK_STYLES[riskLevel].cls}`}>
            {riskLevel}
          </span>
          <p className="text-[11px] text-slate-600 mt-2">
            {zonesAffected > 0 ? `${zonesAffected} zone${zonesAffected !== 1 ? 's' : ''} affected` : 'No active hazards'}
          </p>
        </div>

        <div className="glass-card rounded-xl p-4 border border-white/[0.07]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Active Alerts</span>
            <span className={`w-7 h-7 rounded-lg flex items-center justify-center border ${unacked.length > 0 ? 'bg-hazard/10 border-hazard/25' : 'bg-ember/10 border-ember/25'}`}>
              <Bell size={13} className={unacked.length > 0 ? 'text-hazard' : 'text-ember'} />
            </span>
          </div>
          <p className={`font-raj font-bold text-[26px] leading-none ${activeAlerts.length > 0 ? 'text-hazard' : 'text-white'}`}>{activeAlerts.length}</p>
          <p className={`text-[11px] mt-2 ${unacked.length > 0 ? 'text-hazard' : 'text-slate-600'}`}>
            {unacked.length > 0 ? `${unacked.length} unacknowledged` : 'All acknowledged'}
          </p>
        </div>
      </div>

      {/* ── Recent Incidents ───────────────────────── */}
      <div className="glass-card rounded-xl border border-white/[0.07] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
          <div>
            <h2 className="font-raj font-semibold text-[13px] text-white">Recent Incidents</h2>
            <p className="text-[11px] text-slate-600">Last 5 events</p>
          </div>
          <Link to="/incidents" className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-ember transition-colors">
            View all <ChevronRight size={11} />
          </Link>
        </div>

        {recent.length === 0 ? (
          <LocalDeploymentNotice what="This dashboard">
            <p className="text-center text-slate-700 text-sm py-10">No incidents recorded</p>
          </LocalDeploymentNotice>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-600">
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Camera</th>
                <th className="px-4 py-2 font-medium">Zone</th>
                <th className="px-4 py-2 font-medium">AI Conf.</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {recent.map(a => (
                <tr key={a.alert_id} className="border-t border-white/[0.05] text-[12px]">
                  <td className="px-4 py-2.5 font-mono text-slate-500">
                    {new Date(a.timestamp).toLocaleTimeString('en-US', { hour12: false })}
                  </td>
                  <td className="px-4 py-2.5 text-slate-300">{a.camera_name}</td>
                  <td className="px-4 py-2.5 text-slate-500">{a.zone}</td>
                  <td className="px-4 py-2.5 font-mono text-slate-500">{Math.round(a.confidence * 100)}%</td>
                  <td className="px-4 py-2.5">
                    <StatusPill alert={a} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Recent Alert Camera Preview ───────────── */}
      <div className="glass-card rounded-xl border border-white/[0.07] overflow-hidden">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 px-4 py-3 border-b border-white/[0.06]">
          <h2 className="font-raj font-semibold text-[13px] text-white">Recent Alert Camera Preview</h2>
          {preview && (
            <>
              <span className="text-[11px] text-slate-500">Camera: <span className="text-slate-300">{preview.camera_name}</span></span>
              <span className="text-[11px] text-slate-500">Zone: <span className="text-slate-300">{preview.zone}</span></span>
              <span className="text-[11px] text-slate-500">Status: <span className="text-hazard">{formatHazardLabel(preview.hazard_type)}</span></span>
            </>
          )}
          <Link to="/alerts" className="ml-auto flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-300 transition-colors">
            View all <ChevronRight size={11} />
          </Link>
        </div>

        <div className="p-4">
          {preview?.frame_b64 ? (
            <div className="relative rounded-lg overflow-hidden aspect-video max-w-2xl bg-[#06080D]">
              <img src={`data:image/jpeg;base64,${preview.frame_b64}`} className="w-full h-full object-cover" alt="" />
              <span className="absolute top-2 left-2 flex items-center gap-1 text-[10px] font-raj font-semibold tracking-widest text-white bg-hazard/90 px-2 py-0.5 rounded">
                <span className="w-1.5 h-1.5 rounded-full bg-white live-dot" /> LIVE
              </span>
              <span className="absolute top-2 right-2 font-mono text-[10px] text-white/70 bg-black/50 px-1.5 py-0.5 rounded">
                {new Date(preview.timestamp).toLocaleString()}
              </span>
            </div>
          ) : (
            <p className="text-center text-slate-700 text-sm py-10">No recent alert snapshots</p>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusPill({ alert }) {
  if (alert.status === 'resolved') {
    return <span className="text-[10px] font-raj font-semibold px-2 py-0.5 rounded bg-safe/15 text-safe uppercase">Resolved</span>
  }
  if (alert.status === 'in_progress') {
    return <span className="text-[10px] font-raj font-semibold px-2 py-0.5 rounded bg-warn/15 text-warn uppercase">In Progress</span>
  }
  if (alert.hazard_type === 'camera_offline') {
    return <span className="text-[10px] font-raj font-semibold px-2 py-0.5 rounded bg-white/[0.06] text-slate-400 uppercase">Camera Offline</span>
  }
  return (
    <span className="text-[10px] font-raj font-semibold px-2 py-0.5 rounded bg-hazard/15 text-hazard uppercase">
      {formatHazardLabel(alert.hazard_type)}
    </span>
  )
}
