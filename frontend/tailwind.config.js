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
          bg: '#2a262b',
          sidebar: '#221f23',
          panel: '#221f23',
          panelBorder: '#3d363f',
          card: '#1d1a1e',
          cardBorder: '#3d363f',
          accent: '#9013fe',
          accentHover: '#7c0fd8',
          accentLight: '#a855f7',
          accentMuted: 'rgba(144, 19, 254, 0.15)',
          textMuted: '#94A3B8',
          bullish: '#10B981',
          bearish: '#F43F5E',
        }
      }
    },
  },
  plugins: [],
}
