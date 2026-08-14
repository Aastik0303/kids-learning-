import type { Config } from "tailwindcss";

/**
 * Breakpoints are defined HERE and nowhere else (OP-06 §2).
 *
 * `screens` sits directly on `theme`, not `theme.extend`, so Tailwind's
 * defaults (640/768/1024/1280) are REPLACED rather than merged. Merging is
 * what produced the old conflict: hand-written CSS used 640/900 while
 * Tailwind used its own scale, and the two disagreed at every width between
 * 768 and 900.
 *
 * Mobile-first: every named screen is `min-width`.
 */
const screens = {
  xs: "380px",
  sm: "480px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
  // Raw variants — posture, not size.
  landscape: { raw: "(orientation: landscape)" },
  short: { raw: "(max-height: 480px)" },
  motion: { raw: "(prefers-reduced-motion: no-preference)" }
} as const;

/**
 * Fluid type and spacing resolve to the CSS custom properties defined once in
 * `app/globals.css` :root. The clamp() expressions live there so hand-written
 * CSS and Tailwind utilities read the same scale — no component may carry its
 * own magic numbers.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./services/**/*.{ts,tsx}"],
  theme: {
    screens,
    extend: {
      colors: {
        berry: "#d94f70",
        leaf: "#2f8f6b",
        sunshine: "#f5b84b",
        sky: "#4a90c2",
        ink: "#25313f"
      },
      fontSize: {
        "fluid-xs": "var(--step--2)",
        "fluid-sm": "var(--step--1)",
        "fluid-base": "var(--step-0)",
        "fluid-lg": "var(--step-1)",
        "fluid-xl": "var(--step-2)",
        "fluid-2xl": "var(--step-3)",
        "fluid-3xl": "var(--step-4)"
      },
      spacing: {
        "fluid-1": "var(--space-1)",
        "fluid-2": "var(--space-2)",
        "fluid-3": "var(--space-3)",
        "fluid-4": "var(--space-4)",
        "fluid-5": "var(--space-5)",
        "fluid-6": "var(--space-6)",
        // Safe areas, for padding fixed elements.
        "safe-t": "env(safe-area-inset-top)",
        "safe-r": "env(safe-area-inset-right)",
        "safe-b": "env(safe-area-inset-bottom)",
        "safe-l": "env(safe-area-inset-left)"
      },
      // Touch-target floors per surface (OP-06 §2).
      minWidth: {
        "touch-parent": "var(--touch-parent)",
        "touch-child": "var(--touch-child)",
        "touch-toddler": "var(--touch-toddler)"
      },
      minHeight: {
        "touch-parent": "var(--touch-parent)",
        "touch-child": "var(--touch-child)",
        "touch-toddler": "var(--touch-toddler)"
      },
      boxShadow: {
        soft: "0 14px 40px rgba(37, 49, 63, 0.12)"
      }
    }
  },
  plugins: []
};

export default config;
export { screens };
