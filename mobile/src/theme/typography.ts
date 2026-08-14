import { Platform } from "react-native";

/**
 * The web build leans almost entirely on very heavy weights (800/900) —
 * that chunky, friendly weight is a big part of the brand read, so it
 * carries over here.
 */
export const fontWeight = {
  regular: "500",
  medium: "700",
  bold: "800",
  heavy: "900",
} as const;

export type FontWeightKey = keyof typeof fontWeight;

/** System font stack. Swap `family` here if a brand face is added later. */
export const fontFamily = Platform.select({
  ios: { base: "System", rounded: "System" },
  android: { base: "sans-serif", rounded: "sans-serif-medium" },
  default: { base: "System", rounded: "System" },
});

export type TextVariant =
  | "display"
  | "title"
  | "heading"
  | "subheading"
  | "body"
  | "bodyLarge"
  | "label"
  | "caption"
  | "overline"
  | "childPrompt"
  | "childAnswer"
  | "toddlerPrompt";

type VariantSpec = {
  fontSize: number;
  lineHeight: number;
  fontWeight: (typeof fontWeight)[FontWeightKey];
  letterSpacing?: number;
  textTransform?: "uppercase";
};

/**
 * Base sizes are tuned for a standard phone. `scaleType` in theme.ts
 * multiplies these per breakpoint rather than hardcoding per-screen sizes.
 */
export const typeScale: Record<TextVariant, VariantSpec> = {
  display: { fontSize: 40, lineHeight: 44, fontWeight: fontWeight.heavy, letterSpacing: -0.5 },
  title: { fontSize: 30, lineHeight: 36, fontWeight: fontWeight.heavy, letterSpacing: -0.3 },
  heading: { fontSize: 24, lineHeight: 30, fontWeight: fontWeight.heavy },
  subheading: { fontSize: 19, lineHeight: 25, fontWeight: fontWeight.bold },
  bodyLarge: { fontSize: 17, lineHeight: 25, fontWeight: fontWeight.medium },
  body: { fontSize: 15, lineHeight: 22, fontWeight: fontWeight.medium },
  label: { fontSize: 14, lineHeight: 18, fontWeight: fontWeight.heavy },
  caption: { fontSize: 12, lineHeight: 16, fontWeight: fontWeight.bold },
  overline: {
    fontSize: 11,
    lineHeight: 14,
    fontWeight: fontWeight.heavy,
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },

  // Child-facing variants: bigger, heavier, tighter leading so a whole
  // prompt fits on one screen without scrolling.
  childPrompt: { fontSize: 28, lineHeight: 34, fontWeight: fontWeight.heavy },
  childAnswer: { fontSize: 34, lineHeight: 38, fontWeight: fontWeight.heavy },
  toddlerPrompt: { fontSize: 36, lineHeight: 42, fontWeight: fontWeight.heavy },
};

/**
 * Clamp the OS font-scale setting. Respecting accessibility text sizing is
 * required, but an unbounded 2x scale destroys a fixed activity canvas —
 * so we honour it up to a point and let layout breathe instead.
 */
export function clampFontScale(osFontScale: number): number {
  return Math.min(Math.max(osFontScale, 0.85), 1.35);
}
