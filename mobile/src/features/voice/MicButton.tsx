import { useEffect, useRef } from "react";
import { Animated, Pressable, View } from "react-native";

import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useAudioStore } from "@/store/audioStore";

export type MicButtonProps = {
  onPress: () => void | Promise<void>;
  disabled?: boolean;
  size?: "medium" | "large";
};

/**
 * The single most important control in the app for a pre-reader.
 *
 * It has to answer "is it my turn?" without words, so listening state is
 * carried by an expanding ring plus a colour change, and the button is
 * disabled outright while the avatar is speaking — the child physically
 * cannot open the mic into the guide's own voice.
 */
export function MicButton({ onPress, disabled, size = "medium" }: MicButtonProps) {
  const theme = useTheme();
  const isListening = useAudioStore((state) => state.isListening);
  const isSpeaking = useAudioStore((state) => state.isSpeaking);
  const isSettling = useAudioStore((state) => state.isSettling);

  const ring = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!isListening || theme.reduceMotion) {
      ring.setValue(0);
      return;
    }
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(ring, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(ring, { toValue: 0, duration: 200, useNativeDriver: true }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [isListening, ring, theme.reduceMotion]);

  const diameter = size === "large" ? 132 : 104;
  // Blocked while the guide talks — this is the mic-gating rule made visible.
  const blocked = disabled || isSpeaking || isSettling;

  return (
    <View style={{ alignItems: "center", justifyContent: "center", gap: theme.space[2] }}>
      <View style={{ width: diameter, height: diameter, alignItems: "center", justifyContent: "center" }}>
        {isListening ? (
          <Animated.View
            pointerEvents="none"
            style={{
              position: "absolute",
              width: diameter,
              height: diameter,
              borderRadius: 999,
              borderWidth: 4,
              borderColor: theme.colors.secondary,
              opacity: ring.interpolate({ inputRange: [0, 1], outputRange: [0.7, 0] }),
              transform: [
                { scale: ring.interpolate({ inputRange: [0, 1], outputRange: [1, 1.45] }) },
              ],
            }}
          />
        ) : null}

        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isListening ? "Listening. Tap to stop." : "Tap to speak your answer"}
          accessibilityState={{ disabled: blocked, busy: isListening }}
          disabled={blocked}
          onPress={() => void onPress()}
          style={({ pressed }) => ({
            width: diameter - 16,
            height: diameter - 16,
            borderRadius: 999,
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: isListening ? theme.colors.secondary : theme.colors.accent,
            opacity: blocked ? 0.45 : pressed ? 0.85 : 1,
            ...theme.shadows.float,
          })}
        >
          <Text style={{ fontSize: size === "large" ? 52 : 40 }}>🎤</Text>
        </Pressable>
      </View>

      <Text variant="label" align="center" muted>
        {isSpeaking || isSettling ? "Listen first…" : isListening ? "Speak now!" : "Tap and speak"}
      </Text>
    </View>
  );
}
