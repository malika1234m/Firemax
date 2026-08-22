import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { ShieldAlert, Menu } from 'lucide-react'
import { useAuth } from './context/AuthContext'
import { useOrganization } from './context/OrganizationContext'
import Sidebar from './components/Sidebar'
import logo from './assets/logo.png'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import RequestDemo from './pages/RequestDemo'
import PlatformLogin from './pages/platform/PlatformLogin'
import PlatformConsole from './pages/platform/PlatformConsole'
import Dashboard from './pages/Dashboard'
import GetStarted from './pages/GetStarted'
import GetStartedHA from './pages/GetStartedHA'
import ChooseSetup from './pages/ChooseSetup'
import LiveFeed from './pages/LiveFeed'
import Incidents from './pages/Incidents'
import Alerts from './pages/Alerts'
import HomeDevices from './pages/HomeDevices'
import UsersPage from './pages/Users'
import Cameras from './pages/Cameras'
import Shifts from './pages/Shifts'
import Billing from './pages/Billing'
import Support from './pages/Support'
import Sites from './pages/Sites'
import SettingsLayout from './pages/settings/SettingsLayout'
import ProfileSettings from './pages/settings/ProfileSettings'
import OrganizationSettings from './pages/settings/OrganizationSettings'
import DetectionSettings from './pages/settings/DetectionSettings'
import HomeAssistantSettings from './pages/settings/HomeAssistantSettings'
import ContactsSettings from './pages/settings/ContactsSettings'

function FullScreenLoader() {
  return (
    <div className="min-h-screen bg-void flex items-center justify-center">
      <span className="w-6 h-6 rounded-full border-2 border-brand/30 border-t-brand animate-spin" />
    </div>
  )
}

function AppShell({ children }) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  // Close the mobile drawer whenever the route changes.
  useEffect(() => { setDrawerOpen(false) }, [location.pathname])

  return (
    <div className="min-h-screen bg-void bg-dot-grid flex">
      <Sidebar mobileOpen={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Mobile top bar — hidden on md+ where the sidebar is always visible */}
        <header className="md:hidden sticky top-0 z-30 flex items-center gap-3 h-14 px-4 bg-panel/90 backdrop-blur border-b border-white/[0.06]">
          <button onClick={() => setDrawerOpen(true)} aria-label="Open menu"
                  className="text-slate-300 hover:text-white transition-colors">
            <Menu size={22} />
          </button>
          <div className="flex items-center gap-2">
            <img src={logo} alt="" className="w-7 h-7 rounded-md" />
            <span className="font-raj font-bold text-[16px] text-white">Fireme<span className="text-brand">X</span></span>
          </div>
        </header>
        <main className="flex-1 min-w-0 px-4 sm:px-8 py-6 max-w-screen-2xl">
          {children}
        </main>
      </div>
    </div>
  )
}

/* A brand-new organization has not said how it wants to run FiremeX yet, and
 * almost every page assumes one path or the other — the Home Assistant add-on
 * or the standalone edge agent. Ask once, before showing a guide that might not
 * apply. Only admins are asked; an operator invited to an existing org should
 * never be made to answer an infrastructure question. */
function useSetupRedirect() {
  const { isAdmin } = useAuth()
  const { needsSetupChoice, loading } = useOrganization()
  const location = useLocation()
  return isAdmin && !loading && needsSetupChoice && location.pathname !== '/choose-setup'
}

function ProtectedLayout() {
  const { user, loading } = useAuth()
  const location = useLocation()
  const redirectToChoice = useSetupRedirect()

  if (loading) return <FullScreenLoader />
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (redirectToChoice) return <Navigate to="/choose-setup" replace />

  return <AppShell><Outlet /></AppShell>
}

// The root path is public marketing for signed-out visitors and the
// Dashboard for signed-in users — everything else under ProtectedLayout
// redirects to /login instead.
function RootRoute() {
  const { user, loading } = useAuth()
  const redirectToChoice = useSetupRedirect()

  if (loading) return <FullScreenLoader />
  if (!user) return <Landing />
  if (redirectToChoice) return <Navigate to="/choose-setup" replace />

  return <AppShell><Dashboard /></AppShell>
}

function AdminRoute({ children }) {
  const { isAdmin } = useAuth()
  if (!isAdmin) {
    return (
      <div className="glass-card border border-white/[0.07] rounded-xl p-16 flex flex-col items-center gap-4 text-center max-w-lg mx-auto mt-12">
        <div className="w-14 h-14 rounded-full bg-slate-900 border border-white/[0.06] flex items-center justify-center">
          <ShieldAlert size={22} className="text-slate-700" />
        </div>
        <div>
          <p className="text-slate-300 text-sm font-medium">Admins only</p>
          <p className="text-slate-600 text-xs mt-1">Your account is an Operator — this section is restricted to Admins.</p>
        </div>
      </div>
    )
  }
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/"                element={<RootRoute />}      />
      <Route path="/login"           element={<Login />}          />
      <Route path="/signup"          element={<Signup />}         />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password"  element={<ResetPassword />}  />
      <Route path="/request-demo"    element={<RequestDemo />}    />

      {/* Internal FiremeX platform console — vendor-only, deliberately outside
          the customer app and unlinked from any customer navigation. */}
      <Route path="/platform/login"  element={<PlatformLogin />}   />
      <Route path="/platform"        element={<PlatformConsole />} />

      <Route element={<ProtectedLayout />}>
        <Route path="/choose-setup"  element={<AdminRoute><ChooseSetup /></AdminRoute>} />
        <Route path="/get-started"   element={<AdminRoute><GetStarted /></AdminRoute>} />
        <Route path="/get-started/home-assistant"
               element={<AdminRoute><GetStartedHA /></AdminRoute>} />
        <Route path="/live-feed"     element={<LiveFeed />}    />
        <Route path="/incidents"     element={<Incidents />}   />
        <Route path="/alerts"        element={<Alerts />}      />
        <Route path="/home-devices"  element={<HomeDevices />} />
        <Route path="/users"         element={<AdminRoute><UsersPage /></AdminRoute>} />
        <Route path="/cameras"       element={<AdminRoute><Cameras /></AdminRoute>}   />
        <Route path="/sites"         element={<AdminRoute><Sites /></AdminRoute>}     />
        <Route path="/shifts"        element={<Shifts />}      />
        <Route path="/support"       element={<Support />}     />
        <Route path="/billing"       element={<AdminRoute><Billing /></AdminRoute>}  />
        <Route path="/settings" element={<SettingsLayout />}>
          <Route index                element={<Navigate to="profile" replace />} />
          <Route path="profile"       element={<ProfileSettings />} />
          <Route path="organization"  element={<AdminRoute><OrganizationSettings /></AdminRoute>} />
          <Route path="detection"     element={<AdminRoute><DetectionSettings /></AdminRoute>}    />
          <Route path="home-assistant" element={<AdminRoute><HomeAssistantSettings /></AdminRoute>} />
          <Route path="contacts"      element={<AdminRoute><ContactsSettings /></AdminRoute>}     />
        </Route>
      </Route>
    </Routes>
  )
}
