import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "brand-ink": "#0f172a",
        "brand-teal": "#5a949d",
        "brand-teal-hover": "#4a848d",
        "brand-surface": "#f4f7f8",
        "brand-accent-light": "#dfe9ec",
        "sidebar-hover": "#f0f5f6",
        "sidebar-text": "#64748b",
        "border-subtle": "#d1e0e5",
        "palette-mist": "#d1e0e5",
        "palette-sage": "#aac6c1",
        "palette-teal": "#84b3bb",
        "palette-lavender": "#aba8c9",
        "palette-olive": "#d9d991"
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(0,0,0,0.04), 0 1px 2px -1px rgba(0,0,0,0.03)",
        "card-hover": "0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.03)"
      }
    }
  },
  plugins: []
};

export default config;
