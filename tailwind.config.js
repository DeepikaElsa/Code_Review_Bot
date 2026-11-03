/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Dark navy theme derived from the brand blue #14427D.
        ink: {
          950: '#06172c', // app background (deepest)
          900: '#0a1f38', // side panels
          850: '#0d2744', // cards, composer, bubbles
          800: '#102c4e', // raised surfaces / hover
          700: '#14427D', // brand navy
          600: '#1b5a9c', // brand hover
        },
        sky: '#A6D3EA', // secondary accent, icons, positive
        sand: '#F4CB8E', // primary action, warnings/highlights
        'sand-dark': '#e6b672',
        rose: '#C7A4A3', // tertiary / muted accent
        danger: '#e06b6b', // compile failure (kept clearly red for legibility)
        // Foreground text ramp.
        fg: '#EAF2F9',
        'fg-soft': '#B9D3E6',
        'fg-muted': '#7C9BB6',
      },
    },
  },
  plugins: [],
};
