import { NavLink, Outlet } from 'react-router-dom'
import { User, Lock, Building2, Users } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import PageHeader from '../../components/PageHeader'

const TABS = [
  { to: '/settings/profile',  label: 'Profile',  icon: User,      adminOnly: false },
  { to: '/settings/security', label: 'Security', icon: Lock,      adminOnly: false },
  { to: '/settings/company',  label: 'Company',  icon: Building2, adminOnly: true  },
  { to: '/settings/team',     label: 'Team',     icon: Users,     adminOnly: true  },
]

export default function SettingsLayout() {
  const { isAdmin } = useAuth()

  return (
    <div className="max-w-5xl fade-up">
      <PageHeader title="Account Settings" subtitle="You, your password, your company, and the people you work with." />

      <div className="grid grid-cols-1 md:grid-cols-[190px_1fr] gap-8 items-start">
        <nav className="flex md:flex-col gap-0.5 overflow-x-auto">
          {TABS.filter(t => !t.adminOnly || isAdmin).map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors shrink-0
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
