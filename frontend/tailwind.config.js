/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: '#F7F5FC',
        surface: '#FFFFFF',
        subtle: '#F0ECF9',
        hairline: '#E4E0F0',
        ink: '#121118',
        secondary: '#524E63',
        violet: {
          DEFAULT: '#7C3AED',
          hover: '#6D28D9',
          soft: '#EDE9FE',
        },
        pass: {
          DEFAULT: '#059669',
          wash: '#ECFDF5',
        },
        blocked: {
          DEFAULT: '#E11D48',
          wash: '#FFF1F2',
        }
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
