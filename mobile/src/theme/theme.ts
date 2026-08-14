import type { TextStyle } from "react-native";

import { colors, gradients, inkAlpha, palette, whiteAlpha } from "@/theme/colors";
import { duration, easing, loops } from "@/theme/animations";
import { radius } from "@/theme/radius";
import { shadows } from "@/theme/shadows";
import { gutter, space, touchTarget } from "@/theme/spacing";
import {
  clampFontScale,
  fontFamily,
  fontWeight,
  typeScale,
  type TextVariant,
} from "@/theme/typography";
import {
  contentMaxWidth,
  resolveBreakpoint,
  typeScaleFactor,
  type Breakpoint,
} from "@/theme/breakpoints";

/** The static half of the design system — no layout dependency. */
export const tokens = {
  colors,
  palette,
  inkAlpha,
  whiteAlpha,
  gradients,
  space,
  radius,
  shadows,
  gutter,
  touchTarget,
  fontWeight,
  fontFamily,
  duration,
  easing,
  loops,
} as const;

export type Tokens = typeof tokens;

/**
 * The runtime half — everything that depends on the current viewport.
 * Produced by `ThemeProvider` and read through `useTheme()`.
 */
export type Theme = Tokens & {
  breakpoint: Breakpoint;
  isTablet: boolean;
  isLandscape: boolean;
  /** True on the narrowest phones, where two-column never applies. */
  isCompact: boolean;
  width: number;
  height: number;
  pageGutter: number;
  maxContentWidth: number;
  fontScale: number;
  reduceMotion: boolean;
  /** Resolve a type variant with breakpoint + OS font scaling applied. */
  type: (variant: TextVariant) => TextStyle;
};

export type ThemeInput = {
  width: number;
  height: number;
  fontScale: number;
  reduceMotion: boolean;
};

export function buildTheme({
  width,
  height,
  fontScale,
  reduceMotion,
}: ThemeInput): Theme {
  const isLandscape = width > height;
  // In landscape a phone is still a phone — bucket on the short edge so a
  // rotated handset doesn't get tablet layouts.
  const sizingWidth = isLandscape ? Math.min(width, height) : width;
  const breakpoint = resolveBreakpoint(sizingWidth);
  const isTablet = breakpoint === "tablet" || breakpoint === "largeTablet";
  const scale = clampFontScale(fontScale) * typeScaleFactor[breakpoint];

  const pageGutter = isTablet
    ? breakpoint === "largeTablet"
      ? gutter.large
      : gutter.expanded
    : breakpoint === "smallPhone"
      ? gutter.compact
      : gutter.medium;

  return {
    ...tokens,
    breakpoint,
    isTablet,
    isLandscape,
    isCompact: breakpoint === "smallPhone",
    width,
    height,
    pageGutter,
    maxContentWidth: contentMaxWidth[breakpoint],
    fontScale: scale,
    reduceMotion,
    type: (variant: TextVariant): TextStyle => {
      const spec = typeScale[variant];
      return {
        fontSize: Math.round(spec.fontSize * scale),
        lineHeight: Math.round(spec.lineHeight * scale),
        fontWeight: spec.fontWeight,
        letterSpacing: spec.letterSpacing,
        textTransform: spec.textTransform,
        color: colors.text,
      };
    },
  };
}

export { type Breakpoint, type TextVariant };
