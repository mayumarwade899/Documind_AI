/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Cabinet Grotesk', 'DM Sans', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#f3f0ff',
          100: '#e9e3ff',
          200: '#d5caff',
          300: '#b8a5ff',
          400: '#9575ff',
          500: '#7c4dff',
          600: '#6b2fff',
          700: '#5a1de8',
          800: '#4b18c2',
          900: '#3d159e',
          950: '#240b6b',
        },
        surface: {
          0: '#ffffff',
          50: '#f8f8f9',
          100: '#f1f1f3',
          200: '#e4e4e8',
          300: '#d0d0d6',
          400: '#b8b8c2',
          500: '#8f8f9a',
          600: '#6c6c78',
          700: '#3a3a42',
          800: '#1c1c21',
          850: '#16161a',
          900: '#101013',
          950: '#0a0a0d',
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-right': 'slideInRight 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'thinking': 'thinking 1.4s ease-in-out infinite',
        'stream-cursor': 'streamCursor 0.8s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        slideInRight: { from: { opacity: 0, transform: 'translateX(20px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
        pulseSoft: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.5 } },
        thinking: { '0%,80%,100%': { transform: 'scale(0)', opacity: 0.5 }, '40%': { transform: 'scale(1)', opacity: 1 } },
        streamCursor: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } },
        shimmer: { from: { backgroundPosition: '-200% 0' }, to: { backgroundPosition: '200% 0' } },
      },
      boxShadow: {
        'glow-brand': '0 0 20px rgba(124, 77, 255, 0.3)',
        'glow-sm': '0 0 10px rgba(124, 77, 255, 0.2)',
        'card': '0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.08), 0 8px 32px rgba(0,0,0,0.06)',
      }
    },
  },
  plugins: [],
}
