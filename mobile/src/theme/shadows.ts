import { Platform, type ViewStyle } from "react-native";

/**
 * The web build's soft, wide, low-opacity ink shadows. React Native can't
 * express the exact blur radii on Android, so each level pairs an iOS
 * shadow with a tuned Android elevation.
 */
type ShadowLevel = "none" | "soft" | "card" | "panel" | "float" | "dock";

function shadow(
  opacity: number,
  radius: number,
  offsetY: number,
  elevation: number,
): ViewStyle {
  return Platform.select<ViewStyle>({
    ios: {
      shadowColor: "#25313f",
      shadowOpacity: opacity,
      shadowRadius: radius,
      shadowOffset: { width: 0, height: offsetY },
    },
    android: { elevation },
    default: {
      shadowColor: "#25313f",
      shadowOpacity: opacity,
      shadowRadius: radius,
      shadowOffset: { width: 0, height: offsetY },
    },
  }) as ViewStyle;
}

export const shadows: Record<ShadowLevel, ViewStyle> = {
  none: {},
  /** 0 8px 18px rgba(ink, .10) — chips, tokens, small controls */
  soft: shadow(0.1, 9, 4, 2),
  /** 0 14px 36px rgba(ink, .10) — lift-card */
  card: shadow(0.1, 18, 7, 4),
  /** 0 22px 60px rgba(ink, .12) — surface-panel */
  panel: shadow(0.12, 30, 11, 8),
  /** 0 18px 46px rgba(ink, .16) — map nodes, raised CTAs */
  float: shadow(0.16, 23, 9, 10),
  /** 0 18px 52px rgba(ink, .16) — the avatar dock */
  dock: shadow(0.16, 26, 9, 14),
};
