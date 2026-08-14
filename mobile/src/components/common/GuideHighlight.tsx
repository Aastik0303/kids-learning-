import { useEffect, useRef, type ReactNode } from "react";
import { Animated, View, type ViewStyle } from "react-native";

import { useGuideTarget, type GuideTargetKind } from "@/ai/GuideTargetRegistry";
import { useGuideStore } from "@/store/guideStore";
import { useTheme } from "@/app/providers/ThemeProvider";

export type GuideHighlightProps = {
  children: ReactNode;
  /** Stable id the AI may reference, e.g. "triangle-option", "letter-A". */
  targetId: string;
  kind?: GuideTargetKind;
  /** Plain-language label sent to the agent so it knows what this is. */
  label: string;
  style?: ViewStyle;
};

/**
 * Makes its child AI-addressable and renders the highlight when the guide
 * points at it (spec section 11).
 *
 * Two things happen here:
 *   1. Registration — the id joins the live allowlist while mounted.
 *   2. Presentation — a glowing ring animates *outside* the content, so a
 *      highlight never obscures the thing it is drawing attention to.
 *
 * The stagger for `highlight_sequence` comes from the target's index in
 * the store, matching the web build's `.visual-guide-step-N` delays.
 */
export function GuideHighlight({
  children,
  targetId,
  kind = "visual",
  label,
  style,
}: GuideHighlightProps) {
  const theme = useTheme();
  const ref = useGuideTarget(targetId, kind, label);
  const stepIndex = useGuideStore((state) => state.activeHighlights[targetId]);
  const isActive = stepIndex !== undefined;

  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!isActive || theme.reduceMotion) {
      pulse.setValue(isActive && theme.reduceMotion ? 1 : 0);
      return;
    }

    const delay = (stepIndex ?? 0) * 350;
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: theme.loops.guidePulse.duration / 2,
          delay,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0.35,
          duration: theme.loops.guidePulse.duration / 2,
          useNativeDriver: true,
        }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [isActive, stepIndex, pulse, theme.reduceMotion, theme.loops.guidePulse.duration]);

  return (
    <View ref={ref} collapsable={false} style={style}>
      {isActive ? (
        <Animated.View
          pointerEvents="none"
          style={{
            position: "absolute",
            // Sits outside the content box so nothing is covered.
            top: -6,
            left: -6,
            right: -6,
            bottom: -6,
            borderRadius: theme.radius.card,
            borderWidth: 5,
            borderColor: theme.colors.guideOutline,
            opacity: pulse,
            transform: [
              {
                scale: pulse.interpolate({
                  inputRange: [0, 1],
                  outputRange: [1, 1.04],
                }),
              },
            ],
          }}
        />
      ) : null}
      {children}
    </View>
  );
}
