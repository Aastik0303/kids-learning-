/**
 * Brand palette carried over verbatim from the web prototype
 * (`frontend/app/globals.css` + `frontend/tailwind.config.ts`).
 *
 * These hex values are the product identity — do not swap them for
 * Material/system defaults.
 */

export const palette = {
  // Core five from tailwind.config.ts
  berry: "#d94f70",
  leaf: "#2f8f6b",
  sunshine: "#f5b84b",
  sky: "#4a90c2",
  ink: "#25313f",

  // Supporting tones from globals.css :root
  lavender: "#8b7bd8",
  paper: "#fbfcf6",
  card: "#ffffff",

  // Soft tints used across cards, chips and chat bubbles
  sunLight: "#fff2bd",
  sunPale: "#fff7d9",
  sunToken: "#fff5c7",
  leafLight: "#eef8f2",
  skyLight: "#d8f3ff",
  berryLight: "#fff0f3",
  berryDeep: "#b52e50",
  bark: "#8b6b45",
  moss: "#6fbf7b",

  // Day-sky backdrop stops
  skyTop: "#bfeaff",
  skyMid: "#eaf8ff",
  skyBottom: "#f3fbef",

  white: "#ffffff",
  black: "#000000",
} as const;

/** Ink at partial opacity — the web build leans on this constantly. */
export const inkAlpha = {
  a04: "rgba(37, 49, 63, 0.04)",
  a06: "rgba(37, 49, 63, 0.06)",
  a08: "rgba(37, 49, 63, 0.08)",
  a10: "rgba(37, 49, 63, 0.10)",
  a14: "rgba(37, 49, 63, 0.14)",
  a25: "rgba(37, 49, 63, 0.25)",
  a42: "rgba(37, 49, 63, 0.42)",
  a54: "rgba(37, 49, 63, 0.54)",
  a62: "rgba(37, 49, 63, 0.62)",
  a68: "rgba(37, 49, 63, 0.68)",
} as const;

export const whiteAlpha = {
  a34: "rgba(255, 255, 255, 0.34)",
  a42: "rgba(255, 255, 255, 0.42)",
  a46: "rgba(255, 255, 255, 0.46)",
  a58: "rgba(255, 255, 255, 0.58)",
  a66: "rgba(255, 255, 255, 0.66)",
  a68: "rgba(255, 255, 255, 0.68)",
  a86: "rgba(255, 255, 255, 0.86)",
  a92: "rgba(255, 255, 255, 0.92)",
  a96: "rgba(255, 255, 255, 0.96)",
} as const;

/**
 * Semantic roles. Screens should reach for these rather than `palette`
 * so a future dark/high-contrast mode only has to change one file.
 */
export const colors = {
  // Surfaces
  background: palette.paper,
  surface: palette.card,
  surfaceRaised: whiteAlpha.a96,
  surfaceTranslucent: whiteAlpha.a92,
  surfaceMuted: whiteAlpha.a68,
  surfaceSunken: inkAlpha.a06,
  border: inkAlpha.a08,
  borderStrong: inkAlpha.a14,
  divider: inkAlpha.a10,

  // Text
  text: palette.ink,
  textSecondary: inkAlpha.a68,
  textMuted: inkAlpha.a54,
  textDisabled: inkAlpha.a42,
  textOnBrand: palette.white,

  // Brand roles
  primary: palette.leaf,
  primaryOn: palette.white,
  secondary: palette.sky,
  secondaryOn: palette.white,
  accent: palette.sunshine,
  accentOn: palette.ink,
  highlight: palette.sunshine,

  // Feedback — deliberately gentle, never harsh red
  success: palette.leaf,
  successSoft: palette.leafLight,
  warning: palette.sunshine,
  warningSoft: palette.sunLight,
  danger: palette.berry,
  dangerSoft: palette.berryLight,
  dangerStrong: palette.berryDeep,
  info: palette.sky,
  infoSoft: palette.skyLight,

  // Guide / highlight system
  guideGlow: "rgba(245, 184, 75, 0.72)",
  guideGlowSoft: "rgba(245, 184, 75, 0.24)",
  guideOutline: "rgba(245, 184, 75, 0.82)",

  // Focus ring (accessibility)
  focus: "rgba(245, 184, 75, 0.7)",

  // Rewards
  star: palette.sunshine,
  starTrack: inkAlpha.a10,
  rewardToken: palette.sunToken,

  // Locked / disabled states
  locked: "#d9dde2",
  lockedText: inkAlpha.a42,
} as const;

/** Backdrop gradient stops — the "day sky" behind every child screen. */
export const gradients = {
  daySky: [palette.skyTop, palette.skyMid, palette.skyBottom] as const,
  progressFill: [palette.leaf, palette.sky] as const,
  currentNode: [palette.sunshine, "#ff7ab0", palette.lavender] as const,
  completedNode: [palette.sunLight, palette.sunshine] as const,
  celebration: [palette.sunshine, palette.berry, palette.lavender] as const,
} as const;

/**
 * Per-class visual identity. Keys match backend `path_id` values so a
 * class rendered from the API automatically picks up its colours.
 * Ported from `frontend/data/prototype.ts` (`learningWorlds` / `pathAccents`).
 */
export type ClassVisual = {
  label: string;
  worldName: string;
  icon: string;
  mascot: string;
  tint: string;
  accent: string;
  gradient: readonly [string, string];
  reward: string;
};

export const classVisuals: Record<string, ClassVisual> = {
  numbers: {
    label: "Numbers",
    worldName: "Number Kingdom",
    icon: "🔢",
    mascot: "🐼",
    tint: "#e8f7ff",
    accent: palette.sky,
    gradient: ["rgba(206, 239, 255, 0.64)", "rgba(255, 221, 116, 0.42)"],
    reward: "🏆 Number Crown",
  },
  alphabets: {
    label: "Alphabets",
    worldName: "Alphabet Forest",
    icon: "🔠",
    mascot: "🦉",
    tint: "#eaf8ef",
    accent: palette.leaf,
    gradient: ["rgba(192, 231, 183, 0.66)", "rgba(229, 246, 220, 0.44)"],
    reward: "🌟 Letter Leaf",
  },
  colours: {
    label: "Colours",
    worldName: "Colour Garden",
    icon: "🌈",
    mascot: "🦋",
    tint: "#fff1f5",
    accent: palette.berry,
    gradient: ["rgba(255, 187, 206, 0.5)", "rgba(255, 224, 129, 0.42)"],
    reward: "🎨 Colour Petal",
  },
  shapes: {
    label: "Shapes",
    worldName: "Shape Island",
    icon: "🔺",
    mascot: "🐢",
    tint: "#fffaeb",
    accent: palette.sunshine,
    gradient: ["rgba(255, 233, 151, 0.5)", "rgba(181, 224, 255, 0.44)"],
    reward: "🔷 Shape Gem",
  },
  mixed_final: {
    label: "Mixed Final",
    worldName: "Rainbow Castle",
    icon: "🏰",
    mascot: "🦄",
    tint: "#f3f0ff",
    accent: palette.lavender,
    gradient: ["rgba(225, 213, 255, 0.56)", "rgba(204, 236, 255, 0.42)"],
    reward: "👑 Explorer Crown",
  },
  // Mobile-only classes introduced by the RN build. They have no backend
  // path yet, so they render from local content until endpoints exist.
  words: {
    label: "Words",
    worldName: "Word Meadow",
    icon: "📝",
    mascot: "🐝",
    tint: "#eef8f2",
    accent: palette.leaf,
    gradient: ["rgba(192, 231, 183, 0.6)", "rgba(255, 242, 189, 0.4)"],
    reward: "🍯 Word Jar",
  },
  sentences: {
    label: "Sentences",
    worldName: "Story Bridge",
    icon: "💬",
    mascot: "🐧",
    tint: "#e8f7ff",
    accent: palette.sky,
    gradient: ["rgba(206, 239, 255, 0.6)", "rgba(225, 213, 255, 0.4)"],
    reward: "🌉 Sentence Stone",
  },
  speaking: {
    label: "Speaking",
    worldName: "Echo Hills",
    icon: "🎤",
    mascot: "🦜",
    tint: "#fff1f5",
    accent: palette.berry,
    gradient: ["rgba(255, 187, 206, 0.5)", "rgba(206, 239, 255, 0.42)"],
    reward: "🎵 Song Feather",
  },
  drawing: {
    label: "Drawing",
    worldName: "Paint Puddle",
    icon: "🖍️",
    mascot: "🐙",
    tint: "#fffaeb",
    accent: palette.sunshine,
    gradient: ["rgba(255, 233, 151, 0.5)", "rgba(255, 187, 206, 0.42)"],
    reward: "🖌️ Magic Brush",
  },
  tracing: {
    label: "Tracing",
    worldName: "Trace Trail",
    icon: "✏️",
    mascot: "🐌",
    tint: "#f3f0ff",
    accent: palette.lavender,
    gradient: ["rgba(225, 213, 255, 0.5)", "rgba(229, 246, 220, 0.42)"],
    reward: "✨ Trace Star",
  },
  stories: {
    label: "Stories",
    worldName: "Dream Library",
    icon: "📖",
    mascot: "🦊",
    tint: "#f3f0ff",
    accent: palette.lavender,
    gradient: ["rgba(225, 213, 255, 0.56)", "rgba(255, 242, 189, 0.42)"],
    reward: "📚 Story Key",
  },
};

export const fallbackClassVisual: ClassVisual = {
  label: "Learning",
  worldName: "Learning World",
  icon: "⭐",
  mascot: "🐻",
  tint: palette.leafLight,
  accent: palette.leaf,
  gradient: ["rgba(192, 231, 183, 0.6)", "rgba(206, 239, 255, 0.42)"],
  reward: "⭐ Star",
};

export function classVisual(pathId: string | null | undefined): ClassVisual {
  if (!pathId) return fallbackClassVisual;
  return classVisuals[pathId] ?? fallbackClassVisual;
}
