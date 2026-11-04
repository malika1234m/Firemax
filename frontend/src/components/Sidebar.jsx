import { Link, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Home, KeyRound, CreditCard, Settings, LifeBuoy, LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useOrganization } from '../context/OrganizationContext'
import logo from '../assets/logo.png'
import { roleLabel } from '../lib/format'

// The website is the account: no camera, alert or incident pages. Those live
// in the customer's Home Assistant, and are not to be rebuilt here.
const NAV = [
  { to: '/',               label: 'Overview',                  icon: LayoutDashboard, end: true,  adminOnly: false },
  { to: '/home-assistant', label: 'Home Assistant Connection', icon: Home,            end: false, adminOnly: false },
  // The token and billing endpoints are admin-only.
  { to: '/tokens',         label: 'Access Tokens',             icon: KeyRound,        end: false, adminOnly: true  },
  { to: '/billing',        label: 'Plans & Billing',           icon: CreditCard,      end: false, adminOnly: true  },
  { to: '/settings',       label: 'Account Settings',          icon: Settings,        end: false, adminOnly: false },
  { to: '/support',        label: 'Help & Support',            icon: LifeBuoy,        end: false, adminOnly: false },
]

export default function Sidebar({ mobileOpen = false, onClose = () => {} }) {
  const { user, isAdmin, logout } = useAuth()
  const { org } = useOrganization()
  const navigate = useNavigate()

  const navItems = NAV.filter(item => !item.adminOnly || isAdmin)

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
        className={`w-[232px] shrink-0 h-screen bg-panel border-r border-white/[0.06] flex flex-col
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
          {org.subscription_status === 'trialing' && trialDaysLeft !== null && (
            <Link to="/billing" onClick={onClose}
                  className={`block text-[11px] mt-0.5 hover:underline ${trialDaysLeft <= 3 ? 'text-warn' : 'text-slate-400'}`}>
              {trialDaysLeft} day{trialDaysLeft === 1 ? '' : 's'} left in trial
            </Link>
          )}
          {(org.subscription_status === 'trial_ended' || org.subscription_status === 'past_due') && (
            <Link to="/billing" onClick={onClose} className="block text-[11px] mt-0.5 text-hazard hover:underline">
              {org.subscription_status === 'past_due' ? 'Payment failed — update card' : 'Trial ended — choose a plan'}
            </Link>
          )}
        </div>
      )}

      {/* ── Nav ───────────────────────────────── */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
        {navItems.map(({ to, label, icon: Icon, end }) => (
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
          <p className="text-[10px] text-slate-600 truncate">{roleLabel(user?.role)}</p>
        </div>
        <button onClick={handleLogout} title="Sign out"
                className="text-slate-600 hover:text-hazard transition-colors shrink-0">
          <LogOut size={14} />
        </button>
      </div>
      </aside>
    </>
  )
}
