import { useEffect, useMemo, useState } from 'react'
import { Send, CheckCircle2, Clock, XCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import { apiFetch } from '../lib/api'
import { formatHazardLabel } from '../lib/format'
import PageHeader from '../components/PageHeader'

const PAGE_SIZE = 9

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [stats,  setStats]  = useState(null)
  const [page,   setPage]   = useState(1)

  const load = () => {
    apiFetch('/alerts/?limit=200').then(r => r.json()).then(setAlerts).catch(() => {})
    apiFetch('/alerts/stats').then(r => r.json()).then(setStats).catch(() => {})
  }
  useEffect(() => { load() }, [])

  const totalPages = Math.max(1, Math.ceil(alerts.length / PAGE_SIZE))
  const pageItems   = useMemo(() => alerts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [alerts, page])

  const setAck = async (alertId, acknowledged) => {
    await apiFetch(`/alerts/${alertId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acknowledged }),
    })
    load()
  }

  return (
    <div className="space-y-5 fade-up">
      <PageHeader title="Alerts" subtitle="Notification dispatch & acknowledgement audit" />

      {/* ── Stat strip ─────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Send}         label="Alerts sent"     value={stats?.sent ?? 0}         color="text-slate-300" />
        <StatCard icon={CheckCircle2} label="Acknowledged"    value={stats?.acknowledged ?? 0} color="text-safe" />
        <StatCard icon={Clock}        label="Awaiting ack"    value={stats?.awaiting ?? 0}     color="text-warn" />
        <StatCard icon={XCircle}      label="Delivery failed" value={stats?.failed ?? 0}       color="text-hazard" />
      </div>

      {/* ── Dispatched notifications table ─────────── */}
      <div className="glass-card border border-white/[0.07] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06]">
          <h2 className="font-raj font-semibold text-[13px] text-white">Dispatched Notifications</h2>
          <p className="text-[11px] text-slate-600">Each alert is triggered by a linked incident and sent to assigned personnel</p>
        </div>

        {pageItems.length === 0 ? (
          <p className="text-center text-slate-700 text-sm py-12">No alerts dispatched yet</p>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-600">
                <th className="px-4 py-2.5 font-medium">Timestamp</th>
                <th className="px-4 py-2.5 font-medium">Incident</th>
                <th className="px-4 py-2.5 font-medium">Camera</th>
                <th className="px-4 py-2.5 font-medium">Recipient</th>
                <th className="px-4 py-2.5 font-medium">Channel</th>
                <th className="px-4 py-2.5 font-medium">Acknowledged</th>
              </tr>
            </thead>
            <tbody>
              {pageItems.map(a => (
                <tr key={a.alert_id} className="border-t border-white/[0.05] text-[12px]">
                  <td className="px-4 py-3 font-mono text-slate-500">{new Date(a.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span className="text-slate-300">{formatHazardLabel(a.hazard_type)}</span>{' '}
                    <span className="font-mono text-[10px] text-brand bg-brand/10 border border-brand/20 rounded px-1.5 py-0.5 ml-1">
                      {a.incident_code}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{a.camera_name}</td>
                  <td className="px-4 py-3 text-slate-400">{a.recipient || 'Unassigned'}</td>
                  <td className="px-4 py-3 text-slate-500 uppercase text-[10px] tracking-wide">{a.channel}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => setAck(a.alert_id, true)}
                              className={`text-[10px] font-semibold px-2 py-1 rounded-md border transition-colors
                                ${a.acknowledged ? 'bg-safe/20 text-safe border-safe/30' : 'text-slate-600 border-white/[0.08] hover:text-safe'}`}>
                        Yes
                      </button>
                      <button onClick={() => setAck(a.alert_id, false)}
                              className={`text-[10px] font-semibold px-2 py-1 rounded-md border transition-colors
                                ${!a.acknowledged ? 'bg-warn/20 text-warn border-warn/30' : 'text-slate-600 border-white/[0.08] hover:text-warn'}`}>
                        No
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {alerts.length > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.06] text-[11px] text-slate-600">
            <span>Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, alerts.length)} of {alerts.length} alerts</span>
            <div className="flex items-center gap-1">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                      className="p-1.5 rounded-md border border-white/[0.07] disabled:opacity-30 hover:bg-white/[0.04] transition-colors">
                <ChevronLeft size={12} />
              </button>
              <span className="px-2 font-mono">{page} / {totalPages}</span>
              <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
                      className="p-1.5 rounded-md border border-white/[0.07] disabled:opacity-30 hover:bg-white/[0.04] transition-colors">
                <ChevronRight size={12} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="glass-card rounded-xl p-4 border border-white/[0.07]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        <Icon size={13} className={color} />
      </div>
      <p className={`font-raj font-bold text-[22px] leading-none ${color}`}>{value}</p>
    </div>
  )
}
