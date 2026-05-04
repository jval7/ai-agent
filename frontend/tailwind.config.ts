import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Veridian Clinical — primary teal palette
        "brand-ink": "#181c1d",
        "brand-teal": "#006D77",
        "brand-teal-hover": "#008080",
        // Surface hierarchy (no-border rule — use tonal backgrounds)
        "brand-surface": "#f7fafa",
        "surface-low": "#f1f4f4",
        "surface-container": "#ebeeee",
        "surface-high": "#e6e9e9",
        "surface-highest": "#e0e3e3",
        "surface-white": "#ffffff",
        // Accent / interaction
        "brand-accent-light": "#c3ebe2",
        "brand-accent-muted": "#8df5e4",
        // Sidebar
        "sidebar-hover": "#e1e4e4",
        "sidebar-text": "#40494a",
        // Outline (very faint — only for structural separation)
        "border-subtle": "#bcc9c5",
        "outline-variant": "#bcc9c5",
        // Legacy palette tokens kept for backward compat
        "palette-mist": "#bcc9c5",
        "palette-sage": "#aac6c1",
        "palette-teal": "#70d8c8",
        "palette-lavender": "#aba8c9",
        "palette-olive": "#d9d991"
      },
      fontFamily: {
        // Manrope for headings, Inter for body (mirrors mockup)
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Manrope", "Inter", "sans-serif"],
        headline: ["Manrope", "Inter", "sans-serif"]
      },
      boxShadow: {
        card: "0 0 40px rgba(24,28,29,0.04)",
        "card-sm": "0 0 20px rgba(24,28,29,0.03)",
        "card-hover": "0 4px 24px rgba(24,28,29,0.08)"
      }
    }
  },
  plugins: []
};

export default config;
