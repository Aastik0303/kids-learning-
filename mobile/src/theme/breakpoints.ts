/**
 * Width buckets, measured against the *shortest* edge in portrait and the
 * real width in landscape. Nothing in the app may read raw
 * Dimensions.get("window") — see `useResponsive`.
 */
export const breakpoints = {
  smallPhone: 0,
  phone: 360,
  largePhone: 414,
  tablet: 600,
  largeTablet: 905,
} as const;

export type Breakpoint = keyof typeof breakpoints;

export const breakpointOrder: readonly Breakpoint[] = [
  "smallPhone",
  "phone",
  "largePhone",
  "tablet",
  "largeTablet",
];

export function resolveBreakpoint(width: number): Breakpoint {
  let current: Breakpoint = "smallPhone";
  for (const name of breakpointOrder) {
    if (width >= breakpoints[name]) current = name;
  }
  return current;
}

/** Ordinal comparison so callers can ask `atLeast("tablet")`. */
export function breakpointIndex(name: Breakpoint): number {
  return breakpointOrder.indexOf(name);
}

/**
 * Per-breakpoint multiplier applied to the type scale. Small phones shrink
 * slightly; tablets grow so a lesson stays readable from arm's length.
 */
export const typeScaleFactor: Record<Breakpoint, number> = {
  smallPhone: 0.9,
  phone: 1,
  largePhone: 1.04,
  tablet: 1.15,
  largeTablet: 1.24,
};

/** Content max-width — keeps a lesson from stretching across a tablet. */
export const contentMaxWidth: Record<Breakpoint, number> = {
  smallPhone: 9999,
  phone: 9999,
  largePhone: 9999,
  tablet: 720,
  largeTablet: 900,
};
