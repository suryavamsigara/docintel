/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'San Francisco', 'Inter', 'sans-serif'],
      },
      boxShadow: {
        'apple': '0 4px 24px -6px rgba(0, 0, 0, 0.08), 0 0 1px 0 rgba(0, 0, 0, 0.15)',
        'apple-inset': 'inset 0 2px 4px rgba(0,0,0,0.02)',
      },
      colors: {
        ios: {
          blue: '#007AFF',
          green: '#34C759',
          red: '#FF3B30',
          gray: '#F2F2F7',
          grayDark: '#8E8E93',
        }
      }
    },
  },
  plugins: [],
}