import { useEffect, useRef } from "react";
import { Animated, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { useTheme } from "@/app/providers/ThemeProvider";

export type ProgressBarProps = {
  /** 0–1. Values outside the range are clamped. */
  value: number;
  height?: number;
  accessibilityLabel?: string;
};

/** Ports `.progress-track` / `.progress-fill`, including the leaf→sky fill. */
export function ProgressBar({ value, height, accessibilityLabel }: ProgressBarProps) {
  const theme = useTheme();
  const clamped = Math.min(Math.max(value, 0), 1);
  const width = useRef(new Animated.Value(clamped)).current;

  useEffect(() => {
    Animated.timing(width, {
      toValue: clamped,
      duration: theme.reduceMotion ? 0 : theme.duration.normal,
      // Width is not transform-driven, so this cannot use the native driver.
      useNativeDriver: false,
    }).start();
  }, [clamped, width, theme.reduceMotion, theme.duration.normal]);

  const trackHeight = height ?? 14;

  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={accessibilityLabel}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(clamped * 100) }}
      style={{
        height: trackHeight,
        borderRadius: theme.radius.pill,
        backgroundColor: theme.colors.starTrack,
        overflow: "hidden",
      }}
    >
      <Animated.View
        style={{
          height: "100%",
          width: width.interpolate({
            inputRange: [0, 1],
            outputRange: ["0%", "100%"],
          }),
        }}
      >
        <LinearGradient
          colors={[...theme.gradients.progressFill]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={{ flex: 1, borderRadius: theme.radius.pill }}
        />
      </Animated.View>
    </View>
  );
}
