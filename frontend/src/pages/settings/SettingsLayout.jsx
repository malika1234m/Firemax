import { NavLink, Outlet } from 'react-router-dom'
import { User, Building2, Gauge, PhoneCall, Home } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import PageHeader from '../../components/PageHeader'

const TABS = [
  { to: '/settings/profile',       label: 'Profile',            icon: User,      adminOnly: false },
  { to: '/settings/organization',  label: 'Organization',       icon: Building2, adminOnly: true  },
  { to: '/settings/detection',     label: 'Detection Tuning',   icon: Gauge,     adminOnly: true  },
  { to: '/settings/home-assistant', label: 'Home Assistant',    icon: Home,      adminOnly: true  },
  { to: '/settings/contacts',      label: 'Authority Contacts', icon: PhoneCall, adminOnly: true  },
]

export default function SettingsLayout() {
  const { isAdmin } = useAuth()

  return (
    <div className="max-w-5xl fade-up">
      <PageHeader title="Settings" subtitle="Account, notifications, and system configuration" />

      <div className="grid grid-cols-1 md:grid-cols-[190px_1fr] gap-8 items-start">
        <nav className="space-y-0.5">
          {TABS.filter(t => !t.adminOnly || isAdmin).map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
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

        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
