/**
 * 4pt spacing scale. The web build used rem values against a 16px root,
 * so `space.4 === 1rem` and the visual rhythm carries across unchanged.
 */
export const space = {
  0: 0,
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  7: 28,
  8: 32,
  10: 40,
  12: 48,
  14: 56,
  16: 64,
  20: 80,
  24: 96,
} as const;

/**
 * Minimum tap target. Children this young are imprecise — the spec calls
 * for large touch targets, so we sit well above the 44pt platform floor.
 */
export const touchTarget = {
  /** Parent-facing controls; still meets WCAG 2.5.5. */
  parent: 48,
  /** Standard child-facing control. */
  child: 64,
  /** Toddler mode — one big thing at a time. */
  toddler: 88,
} as const;

/** Horizontal page gutters per breakpoint. */
export const gutter = {
  compact: 16,
  medium: 24,
  expanded: 32,
  large: 40,
} as const;
