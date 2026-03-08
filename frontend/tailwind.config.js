/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#030712',
        'bg-secondary': '#0f172a',
        'bg-card': 'rgba(15, 23, 42, 0.6)',
        'bg-hover': 'rgba(30, 41, 59, 0.8)',
        'border': 'rgba(56, 189, 248, 0.15)',
        'text-primary': '#f1f5f9',
        'text-secondary': '#94a3b8',
        'text-muted': '#64748b',
        'bullish': '#10b981',
        'bearish': '#ef4444',
        'neutral': '#3b82f6',
        'warning': '#f97316',
        'accent': '#a855f7',
        'neon': {
          'cyan': '#22d3ee',
          'blue': '#3b82f6',
          'green': '#10b981',
          'red': '#ef4444',
          'purple': '#a855f7',
          'orange': '#f97316',
        },
        'cyber': {
          '900': '#030712',
          '800': '#0f172a',
          '700': '#1e293b',
          '600': '#334155',
        },
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'sans-serif'],
        'display': ['Rajdhani', 'sans-serif'],
        'mono': ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(34, 211, 238, 0.3)',
        'glow-green': '0 0 20px rgba(16, 185, 129, 0.3)',
        'glow-red': '0 0 20px rgba(239, 68, 68, 0.3)',
        'glow-purple': '0 0 20px rgba(168, 85, 247, 0.3)',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'breathe': 'breathe 2s ease-in-out infinite',
        'fade-in-up': 'fade-in-up 0.5s ease-out forwards',
        'scan': 'scan 3s linear infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 5px currentColor' },
          '50%': { opacity: '0.7', boxShadow: '0 0 20px currentColor, 0 0 30px currentColor' },
        },
        'breathe': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'scan': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
    },
  },
  plugins: [],
}
