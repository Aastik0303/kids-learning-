import { useEffect, useRef } from "react";
import { Animated, View } from "react-native";

import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";

export type StarRowProps = {
  earned: number;
  total?: number;
  size?: number;
  /** Pops each star in sequence. Used on the reward beat. */
  animate?: boolean;
};

/**
 * Stars are the child's core feedback signal, so they get a real
 * entrance — staggered, springy, and skipped entirely under reduce-motion.
 */
export function StarRow({ earned, total = 3, size = 30, animate = false }: StarRowProps) {
  const theme = useTheme();
  const scales = useRef(
    Array.from({ length: total }, () => new Animated.Value(animate ? 0 : 1)),
  ).current;

  useEffect(() => {
    if (!animate) return;
    if (theme.reduceMotion) {
      scales.forEach((scale) => scale.setValue(1));
      return;
    }
    Animated.stagger(
      160,
      scales.map((scale, index) =>
        Animated.spring(scale, {
          toValue: index < earned ? 1 : 0.85,
          useNativeDriver: true,
          bounciness: 14,
        }),
      ),
    ).start();
  }, [animate, earned, scales, theme.reduceMotion]);

  return (
    <View
      accessibilityRole="text"
      accessibilityLabel={`${earned} of ${total} stars`}
      style={{ flexDirection: "row", gap: theme.space[1] }}
    >
      {Array.from({ length: total }, (_, index) => (
        <Animated.View key={index} style={{ transform: [{ scale: scales[index] ?? 1 }] }}>
          <Text
            style={{
              fontSize: size,
              lineHeight: size * 1.15,
              opacity: index < earned ? 1 : 0.28,
            }}
          >
            ⭐
          </Text>
        </Animated.View>
      ))}
    </View>
  );
}
