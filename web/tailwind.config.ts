import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)"],
      },
      maxWidth: {
        "7xl": "76rem",
      },
      colors: {
        brand: {
          DEFAULT: "#1d4ed8",   // blue-700
          dark: "#1e3a8a",      // blue-900
          soft: "#eff6ff",      // blue-50
        },
      },
      lineHeight: {
        snug: "1.45",
        normal: "1.65",
      },
    },
  },
  plugins: [],
};

export default config;
