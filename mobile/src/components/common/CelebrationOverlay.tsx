import { useEffect, useRef } from "react";
import { Animated, Pressable, View } from "react-native";

import { AvatarFace } from "@/components/avatar/AvatarFace";
import { StarRow } from "@/components/common/StarRow";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useUiStore } from "@/store/uiStore";

const AUTO_DISMISS_MS = 2200;

/**
 * The reward moment — stars, level unlocks, certificates.
 *
 * Auto-dismisses so a child is never stuck behind a modal they cannot
 * read their way out of, and is tappable for anyone who wants it gone
 * sooner.
 */
export function CelebrationOverlay() {
  const theme = useTheme();
  const celebration = useUiStore((state) => state.celebration);
  const dismiss = useUiStore((state) => state.dismissCelebration);

  const pop = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!celebration) {
      pop.setValue(0);
      return;
    }

    Animated.spring(pop, {
      toValue: 1,
      useNativeDriver: true,
      bounciness: 12,
      speed: 10,
    }).start();

    const timer = setTimeout(dismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [celebration, pop, dismiss]);

  if (!celebration) return null;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${celebration.title}. Tap to continue.`}
      onPress={dismiss}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(37, 49, 63, 0.45)",
      }}
    >
      <Animated.View
        style={{
          alignItems: "center",
          gap: theme.space[4],
          borderRadius: theme.radius.card,
          backgroundColor: theme.colors.surface,
          paddingHorizontal: theme.space[8],
          paddingVertical: theme.space[8],
          marginHorizontal: theme.space[6],
          ...theme.shadows.panel,
          opacity: pop,
          transform: [{ scale: pop.interpolate({ inputRange: [0, 1], outputRange: [0.75, 1] }) }],
        }}
      >
        <AvatarFace state="celebrating" size={110} />

        <Text variant="title" align="center">
          {celebration.title}
        </Text>

        {celebration.subtitle ? (
          <Text variant="body" align="center" muted>
            {celebration.subtitle}
          </Text>
        ) : null}

        {celebration.stars ? <StarRow earned={celebration.stars} total={3} size={36} animate /> : null}
      </Animated.View>

      <View style={{ position: "absolute", bottom: theme.space[12] }}>
        <Text variant="label" color={theme.palette.white}>
          Tap to keep going
        </Text>
      </View>
    </Pressable>
  );
}
