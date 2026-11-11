/** @type {import('tailwindcss').Config} */

const channel = (token) => `rgb(var(${token}) / <alpha-value>)`;

const scale = (prefix, shades) =>
  Object.fromEntries(shades.map((shade) => [shade, channel(`--${prefix}-${shade}`)]));

const navyShades = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900', '950'];
const tealShades = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900'];

const navyInk = { ...scale('ink-navy', navyShades), DEFAULT: channel('--ink-navy-800') };
const navyChrome = { ...scale('chrome-navy', navyShades), DEFAULT: channel('--chrome-navy-800') };
const tealInk = { ...scale('ink-teal', tealShades), DEFAULT: channel('--ink-teal-600') };
const tealBg = { ...scale('bg-teal', tealShades), DEFAULT: channel('--bg-teal-500') };

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: navyInk,
        teal: tealInk,
        surface: {
          bg: channel('--surface-bg'),
          card: channel('--surface-card'),
          border: channel('--surface-border'),
          borderHover: channel('--surface-border-hover'),
        },
        content: {
          primary: channel('--content-primary'),
          secondary: channel('--content-secondary'),
          muted: channel('--content-muted'),
        },
        amber: {
          DEFAULT: '#D97706',
        },
        danger: {
          DEFAULT: '#DC2626',
        },
      },
      backgroundColor: {
        white: channel('--surface-card'),
        navy: navyChrome,
        teal: tealBg,
      },
      borderColor: {
        navy: navyChrome,
        teal: tealBg,
      },
      gradientColorStops: {
        navy: navyChrome,
        teal: tealBg,
        white: channel('--surface-card'),
      },
      ringColor: {
        navy: navyChrome,
        teal: tealBg,
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        subtle: '0 1px 3px 0 rgba(16, 24, 40, 0.06), 0 1px 2px 0 rgba(16, 24, 40, 0.04)',
        card: '0 2px 6px 0 rgba(20, 42, 67, 0.05), 0 1px 3px 0 rgba(20, 42, 67, 0.03)',
        modal: '0 20px 25px -5px rgba(20, 42, 67, 0.1), 0 10px 10px -5px rgba(20, 42, 67, 0.04)',
      },
    },
  },
  plugins: [],
}

