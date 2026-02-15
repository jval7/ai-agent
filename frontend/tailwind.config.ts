import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "brand-ink": "#0f172a",
        "brand-teal": "#0f766e",
        "brand-surface": "#f8fafc"
      }
    }
  },
  plugins: []
};

export default config;
