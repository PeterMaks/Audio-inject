/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: "#07090e",
          900: "#0a0c14",
          850: "#0e111b",
          800: "#131724",
          700: "#1b2133",
        },
        glass: {
          border: "rgba(255, 255, 255, 0.12)",
          highlight: "rgba(255, 255, 255, 0.22)",
          card: "rgba(255, 255, 255, 0.04)",
          hover: "rgba(255, 255, 255, 0.08)",
          active: "rgba(255, 255, 255, 0.12)",
        },
      },
      fontFamily: {
        sans: ["Segoe UI Variable Display", "Segoe UI", "-apple-system", "BlinkMacSystemFont", "Roboto", "sans-serif"],
        mono: ["Consolas", "Cascadia Code", "Courier New", "monospace"],
      },
      boxShadow: {
        glass: "0 12px 40px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.18)",
        "glass-sm": "0 4px 16px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.15)",
        "glass-glow": "0 0 25px rgba(34, 211, 238, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.25)",
      },
    },
  },
  plugins: [],
};
