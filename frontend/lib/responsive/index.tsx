"use client";

import type { DeviceBucket } from "./breakpoints";
import { useResponsive, useResponsiveValue, type ResponsiveValue } from "./useResponsive";

export { useResponsive, useResponsiveValue };
export type { ResponsiveValue, DeviceBucket };
export * from "./breakpoints";

/**
 * Stack that flips from column to row once there is room. Direction is
 * resolved from the *short edge* bucket, so a phone in landscape keeps
 * stacking rather than being treated as a tablet.
 */
export function AdaptiveStack({
  children,
  direction = { phone: "column", tablet: "row" },
  gap = "var(--space-3)",
  align = "stretch",
  className = ""
}: {
  children: React.ReactNode;
  direction?: ResponsiveValue<"row" | "column">;
  gap?: string;
  align?: React.CSSProperties["alignItems"];
  className?: string;
}) {
  const resolved = useResponsiveValue(direction);
  return (
    <div
      className={className}
      style={{ display: "flex", flexDirection: resolved, gap, alignItems: align, minWidth: 0 }}
    >
      {children}
    </div>
  );
}

/**
 * Grid whose column count is chosen per device bucket. `minmax(0, 1fr)` is
 * deliberate — plain `1fr` lets long words push the track wider than the
 * viewport, which is the classic source of horizontal scroll on a phone.
 */
export function ResponsiveGrid({
  children,
  columns = { phone: 1, tablet: 2, desktop: 3 },
  gap = "var(--space-3)",
  className = ""
}: {
  children: React.ReactNode;
  columns?: ResponsiveValue<number>;
  gap?: string;
  className?: string;
}) {
  const count = useResponsiveValue(columns);
  return (
    <div
      className={className}
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))`,
        gap,
        minWidth: 0
      }}
    >
      {children}
    </div>
  );
}

/**
 * Conditional rendering by device bucket or posture.
 *
 * Note this genuinely unmounts rather than hiding with CSS — use it for
 * things that cost something to render. For purely visual hiding prefer a
 * Tailwind variant, which needs no JS and cannot flicker on hydration.
 */
export function Show({
  children,
  on,
  from,
  until,
  landscape,
  short
}: {
  children: React.ReactNode;
  on?: DeviceBucket | DeviceBucket[];
  from?: DeviceBucket;
  until?: DeviceBucket;
  landscape?: boolean;
  short?: boolean;
}) {
  const { device, isLandscape, isShort, atLeast, below } = useResponsive();

  if (on) {
    const list = Array.isArray(on) ? on : [on];
    if (!list.includes(device)) return null;
  }
  if (from && !atLeast(from)) return null;
  if (until && !below(until)) return null;
  if (landscape !== undefined && landscape !== isLandscape) return null;
  if (short !== undefined && short !== isShort) return null;

  return <>{children}</>;
}
