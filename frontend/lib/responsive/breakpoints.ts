/**
 * Device bucketing for the web app.
 *
 * Ported from `mobile/src/theme/breakpoints.ts`, which measures the **shortest
 * edge** rather than the width. That distinction is the whole point:
 *
 *   a 844x390 phone in landscape has a *width* of 844px. Bucket on width and
 *   it classifies as a tablet, and a 4-year-old holding a phone sideways is
 *   handed a desktop layout.
 *
 * Measuring the short edge reports it as a phone, which is what it is.
 *
 * These buckets are NOT the same thing as the Tailwind `screens` in
 * tailwind.config.ts. Those are width-based CSS breakpoints for styling; this
 * is device classification for layout decisions in TypeScript. Both exist and
 * they answer different questions — do not try to collapse them.
 */

export const shortEdgeBreakpoints = {
  phone: 0,
  tablet: 600,
  desktop: 900
} as const;

export type DeviceBucket = keyof typeof shortEdgeBreakpoints;

export const deviceOrder: readonly DeviceBucket[] = ["phone", "tablet", "desktop"];

/** Resolve a bucket from the short edge of the viewport. */
export function resolveDevice(shortEdge: number): DeviceBucket {
  let current: DeviceBucket = "phone";
  for (const name of deviceOrder) {
    if (shortEdge >= shortEdgeBreakpoints[name]) current = name;
  }
  return current;
}

/** Ordinal comparison so callers can ask `atLeast("tablet")`. */
export function deviceIndex(name: DeviceBucket): number {
  return deviceOrder.indexOf(name);
}
