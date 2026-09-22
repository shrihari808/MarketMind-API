/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Raleway', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
      },
      colors: {
        terminal: {
          bg: '#080C14',
          panel: '#0E1626',
          panelBorder: '#1E293B',
          card: '#131F33',
          cardBorder: '#23354E',
          accent: '#38BDF8',
          textMuted: '#94A3B8',
          bullish: '#10B981',
          bearish: '#F43F5E',
        }
      }
    },
  },
  plugins: [],
}
