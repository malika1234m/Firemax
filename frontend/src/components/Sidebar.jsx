import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Video, AlertTriangle, Bell, Users, Camera, Settings, Home, LogOut, CalendarClock, CreditCard, LifeBuoy, Server } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { apiFetch } from '../lib/api'
import logo from '../assets/logo.png'

const NAV = [
  { to: '/',             label: 'Dashboard',    icon: LayoutDashboard, end: true,  adminOnly: false },
  { to: '/live-feed',    label: 'Live Feed',    icon: Video,           end: false, adminOnly: false },
  { to: '/incidents',    label: 'Incidents',    icon: AlertTriangle,   end: false, adminOnly: false },
  { to: '/alerts',       label: 'Alerts',       icon: Bell,            end: false, adminOnly: false },
  { to: '/home-devices', label: 'Home Devices', icon: Home,            end: false, adminOnly: false },
  { to: '/shifts',       label: 'Shifts',       icon: CalendarClock,   end: false, adminOnly: false },
  { to: '/users',        label: 'Users',        icon: Users,           end: false, adminOnly: true  },
  { to: '/cameras',      label: 'Cameras',      icon: Camera,          end: false, adminOnly: true  },
  { to: '/sites',        label: 'Sites',        icon: Server,          end: false, adminOnly: true  },
  { to: '/billing',      label: 'Billing',      icon: CreditCard,      end: false, adminOnly: true  },
  { to: '/support',      label: 'Support',      icon: LifeBuoy,        end: false, adminOnly: false },
  { to: '/settings',     label: 'Settings',     icon: Settings,        end: false, adminOnly: false },
]

export default function Sidebar({ mobileOpen = false, onClose = () => {} }) {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const [org, setOrg] = useState(null)

  useEffect(() => {
    apiFetch('/organizations/me').then(r => r.ok ? r.json() : null).then(setOrg).catch(() => {})
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const initials = user?.name?.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase() ?? '?'
  const trialDaysLeft = org?.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(org.trial_ends_at) - Date.now()) / 86400_000))
    : null

  return (
    <>
      {/* Backdrop — only on mobile, only when the drawer is open */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden transition-opacity
          ${mobileOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      />

      <aside
        className={`w-[216px] shrink-0 h-screen bg-panel border-r border-white/[0.06] flex flex-col
          fixed top-0 left-0 z-50 transition-transform duration-200
          md:sticky md:z-auto md:translate-x-0
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >

      {/* ── Brand ─────────────────────────────── */}
      <div className="flex items-center gap-2.5 px-5 h-16 shrink-0">
        <img src={logo} alt="FiremeX" className="w-8 h-8 rounded-lg shrink-0" />
        <span className="font-raj font-bold text-[17px] tracking-[0.02em] text-white">
          Fireme<span className="text-brand">X</span>
        </span>
      </div>

      {/* ── Org ───────────────────────────────── */}
      {org && (
        <div className="px-5 pb-3 -mt-1">
          <p className="text-[11px] text-slate-400 font-medium truncate">{org.name}</p>
          {org.plan === 'trial' && trialDaysLeft !== null && (
            <p className={`text-[10px] mt-0.5 ${trialDaysLeft <= 3 ? 'text-hazard' : 'text-slate-600'}`}>
              {trialDaysLeft > 0 ? `${trialDaysLeft}d left in trial` : 'Trial ended'}
            </p>
          )}
        </div>
      )}

      {/* ── Nav ───────────────────────────────── */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
        {NAV.filter(item => !item.adminOnly || isAdmin).map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors
               ${isActive
                 ? 'bg-brand/[0.12] text-brand'
                 : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]'}`
            }
          >
            <Icon size={15} strokeWidth={1.8} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── User footer ───────────────────────── */}
      <div className="flex items-center gap-2.5 px-5 h-16 border-t border-white/[0.06] shrink-0">
        <div className="w-8 h-8 rounded-full bg-brand/15 border border-brand/25 flex items-center justify-center shrink-0">
          <span className="font-raj font-semibold text-[11px] text-brand">{initials}</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] text-slate-200 font-medium truncate">{user?.name}</p>
          <p className="text-[10px] text-slate-600 truncate capitalize">{user?.role}</p>
        </div>
        <button onClick={handleLogout} title="Log out"
                className="text-slate-600 hover:text-hazard transition-colors shrink-0">
          <LogOut size={14} />
        </button>
      </div>
      </aside>
    </>
  )
}
