/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        friction: {
          amber: '#f59e0b',
          red: '#ef4444',
          dark: '#0f0f0f',
          darker: '#080808',
          surface: '#1a1a1a',
          border: '#2a2a2a',
          muted: '#6b7280',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
