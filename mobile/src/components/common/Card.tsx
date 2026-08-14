import type { ReactNode } from "react";
import { View, type ViewStyle } from "react-native";

import { useTheme } from "@/app/providers/ThemeProvider";

export type CardProps = {
  children: ReactNode;
  /** `panel` is the big translucent surface; `lift` is the smaller card. */
  variant?: "panel" | "lift" | "flat" | "tinted";
  tint?: string;
  padded?: boolean;
  style?: ViewStyle;
};

/**
 * The rounded surface that carries the brand. Mirrors the web build's
 * `.surface-panel` / `.lift-card` rules.
 */
export function Card({
  children,
  variant = "lift",
  tint,
  padded = true,
  style,
}: CardProps) {
  const theme = useTheme();

  const base: ViewStyle = {
    borderRadius: theme.radius.card,
    padding: padded ? theme.space[4] : 0,
    overflow: "hidden",
  };

  const byVariant: Record<NonNullable<CardProps["variant"]>, ViewStyle> = {
    panel: {
      backgroundColor: theme.whiteAlpha.a92,
      borderWidth: 1,
      borderColor: theme.colors.border,
      ...theme.shadows.panel,
    },
    lift: {
      backgroundColor: theme.whiteAlpha.a96,
      borderWidth: 1,
      borderColor: theme.colors.border,
      ...theme.shadows.card,
    },
    flat: {
      backgroundColor: theme.colors.surface,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    tinted: {
      backgroundColor: tint ?? theme.palette.leafLight,
      borderWidth: 1,
      borderColor: theme.colors.border,
      ...theme.shadows.soft,
    },
  };

  return <View style={[base, byVariant[variant], style]}>{children}</View>;
}
