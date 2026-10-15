import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        m3: {
          primary: "var(--md-sys-color-primary)",
          "on-primary": "var(--md-sys-color-on-primary)",
          "primary-container": "var(--md-sys-color-primary-container)",
          "on-primary-container": "var(--md-sys-color-on-primary-container)",
          secondary: "var(--md-sys-color-secondary)",
          "on-secondary": "var(--md-sys-color-on-secondary)",
          "secondary-container": "var(--md-sys-color-secondary-container)",
          "on-secondary-container": "var(--md-sys-color-on-secondary-container)",
          surface: "var(--md-sys-color-surface)",
          "surface-low": "var(--md-sys-color-surface-container-low)",
          "surface-container": "var(--md-sys-color-surface-container)",
          "surface-high": "var(--md-sys-color-surface-container-high)",
          "surface-highest": "var(--md-sys-color-surface-container-highest)",
          "on-surface": "var(--md-sys-color-on-surface)",
          "on-surface-variant": "var(--md-sys-color-on-surface-variant)",
          outline: "var(--md-sys-color-outline)",
          "outline-variant": "var(--md-sys-color-outline-variant)",
          error: "var(--md-sys-color-error)",
          "error-container": "var(--md-sys-color-error-container)",
        },
      },
      borderRadius: {
        "m3-xs": "4px",
        "m3-sm": "8px",
        "m3-md": "12px",
        "m3-lg": "16px",
        "m3-xl": "28px",
        "m3-full": "9999px",
      },
    },
  },
  plugins: [],
};
export default config;
