/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ofsted: {
          outstanding: "#16a34a",
          good: "#2563eb",
          requires: "#d97706",
          inadequate: "#dc2626",
        },
      },
    },
  },
  plugins: [],
};
