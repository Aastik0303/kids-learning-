import { useEffect, useRef } from "react";
import { Animated, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useResponsive } from "@/components/responsive/useResponsive";
import { useAudioStore } from "@/store/audioStore";
import { useGuideStore } from "@/store/guideStore";
import { useHandRaise } from "@/features/guide/useHandRaise";
import { voiceController } from "@/features/voice/VoiceController";
import { haptics } from "@/services/audio/haptics";
import { isEnabled } from "@/config/featureFlags";

/**
 * The persistent AI companion (spec section 8). Rendered once, above the
 * child navigator, so it survives every screen change.
 *
 * Layout adapts: docked bottom-right on phones in portrait, and pinned to
 * the side in landscape/tablet where there is room beside the activity
 * (spec section 15).
 */
export function AvatarDock({ visible = true }: { visible?: boolean }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { sideBySideGuide } = useResponsive();

  const message = useGuideStore((state) => state.message);
  const avatarState = useGuideStore((state) => state.avatarState);
  const isThinking = useGuideStore((state) => state.isThinking);
  const doubtPhase = useGuideStore((state) => state.doubtPhase);

  const muted = useAudioStore((state) => state.muted);
  const isSpeaking = useAudioStore((state) => state.isSpeaking);
  const isListening = useAudioStore((state) => state.isListening);
  const partial = useAudioStore((state) => state.partialTranscript);

  const { raiseHand } = useHandRaise();

  const appear = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.spring(appear, {
      toValue: visible ? 1 : 0,
      useNativeDriver: true,
      bounciness: 8,
    }).start();
  }, [visible, appear]);

  if (!visible) return null;

  // While the child is speaking, show the live partial instead of the
  // avatar's last line — they need to see they are being heard.
  const bubbleText = isListening
    ? partial || "I am listening…"
    : isThinking
      ? "Let me think…"
      : message;

  const avatarSize = sideBySideGuide ? 92 : theme.isCompact ? 60 : 72;

  return (
    <Animated.View
      pointerEvents="box-none"
      style={{
        position: "absolute",
        left: sideBySideGuide ? undefined : theme.space[3],
        right: theme.space[3],
        bottom: insets.bottom + theme.space[3],
        top: sideBySideGuide ? insets.top + theme.space[8] : undefined,
        justifyContent: sideBySideGuide ? "flex-end" : undefined,
        maxWidth: sideBySideGuide ? 260 : undefined,
        opacity: appear,
        transform: [
          { translateY: appear.interpolate({ inputRange: [0, 1], outputRange: [40, 0] }) },
        ],
      }}
    >
      <View
        style={{
          flexDirection: sideBySideGuide ? "column" : "row",
          alignItems: sideBySideGuide ? "stretch" : "flex-end",
          gap: theme.space[3],
          borderRadius: theme.radius.xxl,
          borderWidth: 1,
          borderColor: theme.colors.border,
          backgroundColor: theme.whiteAlpha.a96,
          padding: theme.space[3],
          ...theme.shadows.dock,
        }}
      >
        <View style={{ alignItems: "center", gap: theme.space[2] }}>
          <AvatarFace state={isListening ? "listening" : avatarState} size={avatarSize} />

          <View style={{ flexDirection: "row", gap: theme.space[2] }}>
            {/* Mute toggle */}
            <DockButton
              label={muted ? "🔇" : "🔊"}
              accessibilityLabel={muted ? "Turn voice on" : "Turn voice off"}
              onPress={() => {
                useAudioStore.getState().toggleMute();
                if (!muted) void voiceController.stopSpeaking();
              }}
            />

            {/* Hand raise — always reachable during learning (spec 13). */}
            {isEnabled("handRaise") ? (
              <DockButton
                label="✋"
                tone={doubtPhase === "idle" ? "accent" : "active"}
                accessibilityLabel="Raise your hand to ask a question"
                onPress={() => {
                  haptics.tap();
                  void raiseHand();
                }}
              />
            ) : null}
          </View>
        </View>

        {bubbleText ? (
          <View
            style={{
              flex: sideBySideGuide ? undefined : 1,
              minHeight: 52,
              justifyContent: "center",
              borderRadius: theme.radius.xl,
              backgroundColor: isListening ? theme.palette.skyLight : theme.palette.leafLight,
              paddingHorizontal: theme.space[3],
              paddingVertical: theme.space[3],
            }}
          >
            <Text variant="body" numberOfLines={4}>
              {bubbleText}
            </Text>
            {isSpeaking ? <SpeakingDots /> : null}
          </View>
        ) : null}
      </View>
    </Animated.View>
  );
}

function DockButton({
  label,
  onPress,
  accessibilityLabel,
  tone = "quiet",
}: {
  label: string;
  onPress: () => void;
  accessibilityLabel: string;
  tone?: "quiet" | "accent" | "active";
}) {
  const theme = useTheme();
  const background =
    tone === "accent"
      ? theme.palette.sunLight
      : tone === "active"
        ? theme.colors.accent
        : theme.palette.sunPale;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      onPress={onPress}
      style={({ pressed }) => ({
        width: 44,
        height: 44,
        borderRadius: 999,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: background,
        opacity: pressed ? 0.8 : 1,
        ...theme.shadows.soft,
      })}
    >
      <Text style={{ fontSize: 20 }}>{label}</Text>
    </Pressable>
  );
}

/** Three bouncing dots while TTS plays — a pre-reader's "I am talking" cue. */
function SpeakingDots() {
  const theme = useTheme();
  const dots = useRef([0, 1, 2].map(() => new Animated.Value(0))).current;

  useEffect(() => {
    if (theme.reduceMotion) return;
    const animations = dots.map((dot, index) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(index * 140),
          Animated.timing(dot, { toValue: 1, duration: 300, useNativeDriver: true }),
          Animated.timing(dot, { toValue: 0, duration: 300, useNativeDriver: true }),
        ]),
      ),
    );
    animations.forEach((animation) => animation.start());
    return () => animations.forEach((animation) => animation.stop());
  }, [dots, theme.reduceMotion]);

  return (
    <View style={{ flexDirection: "row", gap: 4, marginTop: 6 }}>
      {dots.map((dot, index) => (
        <Animated.View
          key={index}
          style={{
            width: 6,
            height: 6,
            borderRadius: 999,
            backgroundColor: theme.colors.primary,
            transform: [{ translateY: dot.interpolate({ inputRange: [0, 1], outputRange: [0, -4] }) }],
          }}
        />
      ))}
    </View>
  );
}
