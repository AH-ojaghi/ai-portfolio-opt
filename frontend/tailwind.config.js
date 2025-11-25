/** @type {import('tailwindcss').Config} */
export default {
  content: [
    \"./index.html\",
    \"./src/**/*.{js,ts,jsx,tsx}\",
  ],
  theme: {
    extend: {
      colors: {
        'fin-dark': '#0f172a',
        'fin-card': '#1e293b',
        'fin-accent': '#10b981',
      }
    },
  },
  plugins: [],
}
