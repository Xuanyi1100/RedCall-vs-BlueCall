/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'scammer-red': '#ef4444',
        'senior-blue': '#3b82f6',
        'dark-bg': '#0f172a',
        'dark-card': '#1e293b',
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'speaking': 'speaking 1.5s ease-in-out infinite',
      },
      keyframes: {
        speaking: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(74, 222, 128, 0.4)' },
          '50%': { boxShadow: '0 0 0 15px rgba(74, 222, 128, 0)' },
        },
      },
    },
  },
  plugins: [],
}
