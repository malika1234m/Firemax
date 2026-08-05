export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        raj:  ['Rajdhani', 'sans-serif'],
        sans: ['DM Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        void:   '#06080D',
        panel:  '#0B0F16',
        hazard: { DEFAULT: '#EF4444', dim: 'rgba(239,68,68,0.12)', glow: 'rgba(239,68,68,0.25)' },
        live:   '#22D3EE',
        warn:   '#F59E0B',
        safe:   '#10B981',
        brand:  { DEFAULT: '#C2410C', dim: 'rgba(194,65,12,0.12)', glow: 'rgba(194,65,12,0.25)' },
        ember:  { DEFAULT: '#C2410C', dim: 'rgba(194,65,12,0.12)', dark: '#9A3412' },
      },
      animation: {
        'hazard-pulse': 'hazard-pulse 2s ease-in-out infinite',
        'live-blink':   'live-blink 1.6s ease-in-out infinite',
        'fade-up':      'fade-up 0.4s ease-out both',
        'slide-in':     'slide-in 0.3s ease-out both',
        'spin-slow':    'spin 2s linear infinite',
      },
      keyframes: {
        'hazard-pulse': {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(239,68,68,0.35), 0 0 20px rgba(239,68,68,0.08)' },
          '50%':     { boxShadow: '0 0 0 6px rgba(239,68,68,0), 0 0 40px rgba(239,68,68,0.20)' },
        },
        'live-blink': {
          '0%,100%': { opacity: '1' },
          '50%':     { opacity: '0.2' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to:   { opacity: '1', transform: 'translateY(0)'    },
        },
        'slide-in': {
          from: { opacity: '0', transform: 'translateX(12px)' },
          to:   { opacity: '1', transform: 'translateX(0)'    },
        },
      },
    },
  },
  plugins: [],
}
