import type { Config } from "tailwindcss";

const HIERARCHY_COLORS = [
  "violet", "fuchsia", "indigo", "blue", "sky",
  "teal", "emerald", "amber", "orange", "slate",
];

// Tailwind는 동적 className을 못 잡으므로 위계 색상 클래스를 미리 safelist에 등록.
const SAFELIST = HIERARCHY_COLORS.flatMap((c) => [
  `bg-${c}-50`,
  `bg-${c}-100`,
  `bg-${c}-500`,
  `bg-${c}-600`,
  `bg-${c}-700`,
  `text-${c}-700`,
  `text-${c}-800`,
  `border-${c}-300`,
  `border-${c}-400`,
  `border-${c}-500`,
  `ring-${c}-200`,
  `ring-${c}-300`,
  `hover:ring-${c}-300`,
]);

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  safelist: SAFELIST,
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
          DEFAULT: "#1d4ed8",
          dark:    "#1e3a8a",
          soft:    "#eff6ff",
        },
      },
      lineHeight: {
        snug:   "1.45",
        normal: "1.65",
      },
    },
  },
  plugins: [],
};

export default config;
