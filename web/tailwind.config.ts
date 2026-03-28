import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // 音乐主题绿色系
        emerald: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
          950: '#052e16',
        },
        dark: {
          primary: '#0f1410',
          secondary: '#1a1f1a',
          tertiary: '#252b25',
        },
        light: {
          primary: '#faf9f5',
          secondary: '#f5f4f0',
          tertiary: '#eeefe8',
        },
        accent: {
          orange: '#d97757',
          blue: '#6a9bcc',
        },
      },
      fontFamily: {
        sans: ['Geist', 'Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'gradient': 'gradient 8s linear infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        gradient: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
        glow: {
          '0%': { boxShadow: '0 0 20px rgba(16, 185, 129, 0.3)' },
          '100%': { boxShadow: '0 0 40px rgba(16, 185, 129, 0.6)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-mesh': `
          radial-gradient(at 40% 20%, rgba(16, 185, 129, 0.3) 0px, transparent 50%),
          radial-gradient(at 80% 0%, rgba(26, 163, 156, 0.3) 0px, transparent 50%),
          radial-gradient(at 0% 50%, rgba(16, 185, 129, 0.2) 0px, transparent 50%),
          radial-gradient(at 80% 50%, rgba(16, 185, 129, 0.15) 0px, transparent 50%),
          radial-gradient(at 0% 100%, rgba(26, 163, 156, 0.2) 0px, transparent 50%)
        `,
      },
    },
  },
  plugins: [],
}
export default config
