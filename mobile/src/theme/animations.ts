import { Easing } from "react-native-reanimated";

/**
 * Motion tokens. Durations match the web build's transitions so the app
 * feels like the same product in motion, not just in colour.
 */
export const duration = {
  instant: 120,
  fast: 180,
  normal: 260,
  slow: 420,
  /** Celebration / reward moments get room to land. */
  celebrate: 900,
  /** Ambient looping motion (float, drift, breathe). */
  ambient: 3800,
} as const;

export const easing = {
  standard: Easing.bezier(0.4, 0, 0.2, 1),
  decelerate: Easing.out(Easing.cubic),
  accelerate: Easing.in(Easing.cubic),
  gentle: Easing.inOut(Easing.sin),
  bounce: Easing.bezier(0.34, 1.56, 0.64, 1),
} as const;

/** Named loops used by the avatar and guide highlight system. */
export const loops = {
  idleFloat: { distance: 3, duration: duration.ambient },
  gentleBounce: { distance: 9, duration: 1800 },
  guidePulse: { min: 1, max: 1.06, duration: 1550 },
  wave: { degrees: 22, duration: 900 },
  think: { degrees: 3, duration: 1400 },
  celebrate: { scale: 1.035, distance: 7, duration: duration.celebrate },
  sparkle: { duration: 1500 },
} as const;
