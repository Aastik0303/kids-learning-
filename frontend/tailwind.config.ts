import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./services/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        berry: "#d94f70",
        leaf: "#2f8f6b",
        sunshine: "#f5b84b",
        sky: "#4a90c2",
        ink: "#25313f"
      },
      boxShadow: {
        soft: "0 14px 40px rgba(37, 49, 63, 0.12)"
      }
    }
  },
  plugins: []
};

export default config;
