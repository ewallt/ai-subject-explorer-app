/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}", // Scan HTML and all JS/TS/JSX files in src/
  ],
  theme: {
    extend: {}, // You can customize Tailwind's theme here later
  },
  plugins: [], // You can add Tailwind plugins here later
}
