import { useEffect, useRef } from "react";
import { Animated, View } from "react-native";

import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import type { AvatarState } from "@/types/domain";

export type AvatarFaceProps = {
  state: AvatarState;
  size?: number;
};

/**
 * The guide character, rebuilt from the web build's CSS avatar
 * (`.avatar-face`, `.avatar-ear`, `.avatar-paw`, …) using RN views.
 *
 * Kept as drawn primitives rather than an image so it scales cleanly from
 * a 56pt dock to a 160pt hero without assets, and so each state can move
 * an individual feature (the waving paw, the thinking tilt).
 */
export function AvatarFace({ state, size = 84 }: AvatarFaceProps) {
  const theme = useTheme();

  const idle = useRef(new Animated.Value(0)).current;
  const wave = useRef(new Animated.Value(0)).current;
  const tilt = useRef(new Animated.Value(0)).current;
  const pop = useRef(new Animated.Value(0)).current;

  const isSpeaking = state === "speaking" || state === "waving";
  const isThinking = state === "thinking";
  const isCelebrating = state === "celebrating" || state === "happy";
  const isListening = state === "listening";

  // Ambient float — always running unless motion is reduced.
  useEffect(() => {
    if (theme.reduceMotion) return;
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(idle, {
          toValue: 1,
          duration: theme.loops.idleFloat.duration / 2,
          useNativeDriver: true,
        }),
        Animated.timing(idle, {
          toValue: 0,
          duration: theme.loops.idleFloat.duration / 2,
          useNativeDriver: true,
        }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [idle, theme.reduceMotion, theme.loops.idleFloat.duration]);

  useEffect(() => {
    if (theme.reduceMotion || !isSpeaking) {
      wave.setValue(0);
      return;
    }
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(wave, { toValue: 1, duration: 450, useNativeDriver: true }),
        Animated.timing(wave, { toValue: 0, duration: 450, useNativeDriver: true }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [isSpeaking, wave, theme.reduceMotion]);

  useEffect(() => {
    if (theme.reduceMotion || !isThinking) {
      tilt.setValue(0);
      return;
    }
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(tilt, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(tilt, { toValue: -1, duration: 700, useNativeDriver: true }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [isThinking, tilt, theme.reduceMotion]);

  useEffect(() => {
    if (theme.reduceMotion || !isCelebrating) {
      pop.setValue(0);
      return;
    }
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(pop, { toValue: 1, duration: 450, useNativeDriver: true }),
        Animated.timing(pop, { toValue: 0, duration: 450, useNativeDriver: true }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [isCelebrating, pop, theme.reduceMotion]);

  // Proportions are expressed as fractions of `size` so the character
  // stays on-model at any scale.
  const u = size / 84;
  const ink = theme.palette.ink;

  return (
    <Animated.View
      accessibilityRole="image"
      accessibilityLabel={`Learning guide, ${state}`}
      style={{
        width: size,
        height: size,
        transform: [
          {
            translateY: Animated.add(
              idle.interpolate({ inputRange: [0, 1], outputRange: [0, -3 * u] }),
              pop.interpolate({ inputRange: [0, 1], outputRange: [0, -6 * u] }),
            ),
          },
          {
            rotate: tilt.interpolate({
              inputRange: [-1, 1],
              outputRange: ["-3deg", "3deg"],
            }),
          },
          { scale: pop.interpolate({ inputRange: [0, 1], outputRange: [1, 1.04] }) },
        ],
      }}
    >
      {/* Ears */}
      <View
        style={{
          position: "absolute",
          left: 3 * u,
          top: 1 * u,
          width: 25 * u,
          height: 25 * u,
          borderRadius: 999,
          backgroundColor: ink,
        }}
      />
      <View
        style={{
          position: "absolute",
          right: 3 * u,
          top: 1 * u,
          width: 25 * u,
          height: 25 * u,
          borderRadius: 999,
          backgroundColor: ink,
        }}
      />

      {/* Face */}
      <View
        style={{
          position: "absolute",
          inset: 7 * u,
          borderRadius: size * 0.45,
          backgroundColor: theme.palette.white,
          borderWidth: 2 * u,
          borderColor: ink,
          overflow: "hidden",
        }}
      >
        {/* Eyes — squint when listening so the state reads at a glance. */}
        <View
          style={{
            position: "absolute",
            left: 13 * u,
            top: isListening ? 24 * u : 20 * u,
            width: 10 * u,
            height: isListening ? 4 * u : 13 * u,
            borderRadius: 999,
            backgroundColor: ink,
          }}
        />
        <View
          style={{
            position: "absolute",
            right: 13 * u,
            top: isListening ? 24 * u : 20 * u,
            width: 10 * u,
            height: isListening ? 4 * u : 13 * u,
            borderRadius: 999,
            backgroundColor: ink,
          }}
        />

        {/* Cheeks */}
        <View
          style={{
            position: "absolute",
            left: 5 * u,
            top: 33 * u,
            width: 9 * u,
            height: 5 * u,
            borderRadius: 999,
            backgroundColor: "rgba(217, 79, 112, 0.35)",
          }}
        />
        <View
          style={{
            position: "absolute",
            right: 5 * u,
            top: 33 * u,
            width: 9 * u,
            height: 5 * u,
            borderRadius: 999,
            backgroundColor: "rgba(217, 79, 112, 0.35)",
          }}
        />

        {/* Nose */}
        <View
          style={{
            position: "absolute",
            alignSelf: "center",
            top: 31 * u,
            width: 7 * u,
            height: 5 * u,
            borderRadius: 999,
            backgroundColor: ink,
          }}
        />

        {/* Mouth — an open O while speaking, a smile otherwise. */}
        <View
          style={{
            position: "absolute",
            alignSelf: "center",
            top: 37 * u,
            width: isSpeaking ? 10 * u : 12 * u,
            height: isSpeaking ? 10 * u : 6 * u,
            borderRadius: 999,
            ...(isSpeaking
              ? { backgroundColor: theme.palette.berry }
              : {
                  borderBottomWidth: 3 * u,
                  borderColor: ink,
                  borderBottomLeftRadius: 999,
                  borderBottomRightRadius: 999,
                }),
          }}
        />
      </View>

      {/* Waving paw */}
      <Animated.View
        style={{
          position: "absolute",
          right: 2 * u,
          bottom: 2 * u,
          width: 18 * u,
          height: 15 * u,
          borderRadius: 999,
          backgroundColor: ink,
          transform: [
            {
              rotate: wave.interpolate({
                inputRange: [0, 1],
                outputRange: ["0deg", "-24deg"],
              }),
            },
            { translateY: wave.interpolate({ inputRange: [0, 1], outputRange: [0, -4 * u] }) },
          ],
        }}
      />
      <View
        style={{
          position: "absolute",
          left: 2 * u,
          bottom: 2 * u,
          width: 18 * u,
          height: 15 * u,
          borderRadius: 999,
          backgroundColor: ink,
        }}
      />

      {/* Celebration sparkles */}
      {isCelebrating ? (
        <>
          <Text style={{ position: "absolute", right: -2 * u, top: 0, fontSize: 16 * u }}>✨</Text>
          <Text style={{ position: "absolute", left: -3 * u, top: 12 * u, fontSize: 13 * u }}>
            ✨
          </Text>
        </>
      ) : null}
    </Animated.View>
  );
}
