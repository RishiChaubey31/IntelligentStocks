/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["JetBrains Mono", "monospace"],
      },
      colors: {
        surface: "#0f0f12",
        card: "#16161a",
        border: "#2a2a2e",
        accent: "#7c3aed",
        buy: "#22c55e",
        sell: "#ef4444",
        hold: "#94a3b8",
      },
    },
  },
  plugins: [],
};
