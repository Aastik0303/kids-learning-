/**
 * Rounded, playful surfaces are core to the brand — the web build never
 * uses a sharp corner on a content surface. Values mirror the rem radii
 * in `globals.css` at a 16px root.
 */
export const radius = {
  xs: 6,
  sm: 10,
  md: 16,
  lg: 20,
  xl: 24,
  /** 1.75rem — avatar dock */
  xxl: 28,
  /** 2rem — the signature card/panel radius */
  card: 32,
  /** Fully rounded pill / circle */
  pill: 999,
} as const;
