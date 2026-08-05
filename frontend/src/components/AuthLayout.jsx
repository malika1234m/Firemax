import authHero from '../assets/auth-hero.png'
import logo from '../assets/logo.png'

export default function AuthLayout({ heading, subheading, children, footer }) {
  return (
    <div className="min-h-screen w-full relative flex items-center justify-end px-6 sm:px-12 lg:px-20 py-10 overflow-hidden">
      <div
        className="absolute inset-0 bg-cover bg-center"
        style={{ backgroundImage: `url(${authHero})` }}
      />
      <div className="absolute inset-0 bg-void/70" />
      <div className="absolute inset-0 bg-gradient-to-r from-black/96 via-black/88 to-black/70" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-black/40" />

      {/* ── Branding, left side ─────────────────────────── */}
      <div className="absolute left-6 sm:left-12 lg:left-20 top-1/2 -translate-y-1/2 max-w-md hidden md:block">
        <div className="flex items-center gap-2 mb-6">
          <span className="w-8 h-0.5 bg-ember rounded-full" />
          <span className="w-1.5 h-1.5 rounded-full bg-ember/70" />
        </div>
        <h1 className="font-raj font-extrabold text-[42px] lg:text-[52px] leading-none tracking-tight">
          <span className="text-ember">FIRE</span><span className="text-white">meX</span>
        </h1>
        <p className="text-slate-200 text-[16px] lg:text-[18px] mt-4 font-light">
          Secure Monitoring &amp; Instant Alerts
        </p>
      </div>

      {/* ── Card, right side ────────────────────────────── */}
      <div className="glass-card relative w-full max-w-[420px] rounded-2xl border border-white/[0.08] shadow-2xl shadow-black/60 p-8 sm:p-9">
        <div className="flex items-center gap-2.5 mb-7">
          <img src={logo} alt="FiremeX" className="w-9 h-9 rounded-lg" />
          <span className="font-raj font-bold text-[19px] text-white">FiremeX</span>
        </div>

        <h2 className="font-raj font-bold text-[22px] text-white">{heading}</h2>
        {subheading && <p className="text-[13px] text-slate-500 mt-1 mb-6">{subheading}</p>}
        {!subheading && <div className="mb-6" />}

        {children}

        {footer && <div className="mt-6 text-center text-[13px] text-slate-500">{footer}</div>}
      </div>
    </div>
  )
}
