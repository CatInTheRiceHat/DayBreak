/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        title: ["'Abril Fatface'", "serif"],
        heading: ["'Story Script'", "sans-serif"],
        body: ["'Montserrat'", "sans-serif"],
      },
      colors: {
        background:        '#FAF9F6',
        foreground:        '#2B2631',
        card:              '#FAF9F6',
        'card-foreground': '#2B2631',
        primary:           '#7C6D8C',
        'primary-foreground': '#FAF9F6',
        secondary:         '#CFCBD3',
        'secondary-foreground': '#2B2631',
        muted:             '#CFCBD3',
        'muted-foreground':'#938E97',
        accent:            '#AD9EB8',
        'accent-foreground':'#2B2631',
        border:            '#B0ACB5',
        input:             '#CFCBD3',
        ring:              '#7C6D8C',
      },
      borderRadius: {
        'full': '9999px',
      },
      animation: {
        'float':       'float 6s ease-in-out infinite',
        'shimmer':     'shimmer 5s ease infinite',
        'mesh-shift':  'meshShift 14s ease-in-out infinite alternate',
        'count-up':    'countUp 1s ease-out forwards',
        'fade-up':     'fadeUp 0.7s ease-out forwards',
        'pulse-soft':  'pulseSoft 3s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-12px)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '0% 50%' },
          '50%':  { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        meshShift: {
          '0%':   { backgroundSize: '100% 100%, 100% 100%, 100% 100%, 100% 100%' },
          '100%': { backgroundSize: '110% 110%, 105% 108%, 108% 105%, 112% 110%' },
        },
        fadeUp: {
          '0%':   { opacity: '0', transform: 'translateY(24px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '0.6' },
          '50%':      { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
