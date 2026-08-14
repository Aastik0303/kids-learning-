import type { ReactNode } from "react";
import { ScrollView, View, type ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/app/providers/ThemeProvider";

export type ScreenProps = {
  children: ReactNode;
  /** Scrollable by default; lesson screens opt out to keep a fixed canvas. */
  scroll?: boolean;
  /** Paints the day-sky gradient behind the content. */
  backdrop?: boolean;
  /** Extra bottom padding so the avatar dock never covers content. */
  reserveDockSpace?: boolean;
  contentStyle?: ViewStyle;
  style?: ViewStyle;
};

/** Height the avatar dock occupies at the bottom of child screens. */
export const DOCK_RESERVE = 132;

/**
 * Page shell. Owns safe areas, the day-sky backdrop, the content max-width
 * on tablets, and the space reserved for the persistent avatar.
 */
export function Screen({
  children,
  scroll = true,
  backdrop = true,
  reserveDockSpace = false,
  contentStyle,
  style,
}: ScreenProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();

  const padding: ViewStyle = {
    paddingHorizontal: theme.pageGutter,
    paddingTop: insets.top + theme.space[3],
    paddingBottom: insets.bottom + theme.space[6] + (reserveDockSpace ? DOCK_RESERVE : 0),
  };

  const constrained: ViewStyle = {
    width: "100%",
    maxWidth: theme.maxContentWidth,
    alignSelf: "center",
  };

  const body = scroll ? (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={[padding, contentStyle]}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <View style={constrained}>{children}</View>
    </ScrollView>
  ) : (
    <View style={[{ flex: 1 }, padding, contentStyle]}>
      <View style={[constrained, { flex: 1 }]}>{children}</View>
    </View>
  );

  return (
    <View style={[{ flex: 1, backgroundColor: theme.colors.background }, style]}>
      {backdrop ? (
        <LinearGradient
          colors={[...theme.gradients.daySky]}
          locations={[0, 0.42, 1]}
          style={{ position: "absolute", inset: 0 }}
          pointerEvents="none"
        />
      ) : null}
      {body}
    </View>
  );
}
