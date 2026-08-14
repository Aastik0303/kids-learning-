import { useEffect, useRef } from "react";
import { Animated, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useUiStore } from "@/store/uiStore";

/**
 * Connectivity notice (spec section 20).
 *
 * Worded for a child, not an engineer — "I cannot hear the internet" beats
 * "Network unavailable" when the reader is four. It never blocks the
 * screen: cached content stays usable underneath.
 */
export function OfflineBanner() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();

  const isOnline = useUiStore((state) => state.isOnline);
  const isBackendReachable = useUiStore((state) => state.isBackendReachable);

  const visible = !isOnline || !isBackendReachable;
  const slide = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(slide, {
      toValue: visible ? 1 : 0,
      duration: theme.reduceMotion ? 0 : theme.duration.normal,
      useNativeDriver: true,
    }).start();
  }, [visible, slide, theme.reduceMotion, theme.duration.normal]);

  if (!visible) return null;

  return (
    <Animated.View
      pointerEvents="none"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        paddingTop: insets.top + theme.space[2],
        paddingBottom: theme.space[2],
        paddingHorizontal: theme.space[4],
        backgroundColor: theme.palette.sunLight,
        opacity: slide,
        transform: [{ translateY: slide.interpolate({ inputRange: [0, 1], outputRange: [-60, 0] }) }],
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[2] }}>
        <Text style={{ fontSize: 18 }}>🌧️</Text>
        <Text variant="label" style={{ flex: 1 }}>
          {isOnline
            ? "I cannot reach the lessons right now."
            : "I cannot hear the internet right now."}
        </Text>
      </View>
    </Animated.View>
  );
}
