import type { Config } from 'tailwindcss'

// Preflight отключён: базовые стили и компоненты приходят из перенесённого style.css,
// Tailwind используется для утилит поверх (токены совпадают с оригиналом).
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  corePlugins: { preflight: false },
  theme: {
    extend: {
      colors: { ink: '#0c0c0c', paper: '#f4f4f4', muted: '#a5a5a5', alert: '#ff443b' },
      fontFamily: { display: ['Unbounded', 'Arial', 'sans-serif'], body: ['Raleway', 'Arial', 'sans-serif'] },
    },
  },
} satisfies Config
