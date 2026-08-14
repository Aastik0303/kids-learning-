import type { ReactNode } from "react";
import { View, type ViewStyle } from "react-native";

import { useResponsive } from "@/components/responsive/useResponsive";
import { useTheme } from "@/app/providers/ThemeProvider";

type AdaptiveStackProps = {
  children: ReactNode;
  /** Flex weights applied to each child when the stack goes horizontal. */
  weights?: number[];
  gap?: number;
  /** Force a direction instead of deriving it from the viewport. */
  direction?: "row" | "column";
  style?: ViewStyle;
};

/**
 * Column on phones, row when there's width to spare. This is the primitive
 * behind "landscape puts the avatar beside the activity" — the lesson
 * screen wraps its guide panel and activity canvas in one of these.
 */
export function AdaptiveStack({
  children,
  weights,
  gap,
  direction,
  style,
}: AdaptiveStackProps) {
  const theme = useTheme();
  const { sideBySideGuide } = useResponsive();
  const resolved = direction ?? (sideBySideGuide ? "row" : "column");
  const gutter = gap ?? theme.space[4];

  const items = Array.isArray(children) ? children : [children];

  return (
    <View
      style={[
        {
          flexDirection: resolved,
          gap: gutter,
          alignItems: resolved === "row" ? "stretch" : undefined,
        },
        style,
      ]}
    >
      {items.map((child, index) => (
        <View key={index} style={{ flex: resolved === "row" ? (weights?.[index] ?? 1) : undefined }}>
          {child}
        </View>
      ))}
    </View>
  );
}
