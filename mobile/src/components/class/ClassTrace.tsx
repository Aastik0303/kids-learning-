import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, View } from "react-native";

import { Text } from "@/components/common/Text";
import { DrawingCanvas } from "@/features/drawing/DrawingCanvas";
import { scaleTarget, traceTargetFor } from "@/features/tracing/tracePaths";
import { scoreTrace, traceFeedback } from "@/features/tracing/strokeScoring";
import { useTheme } from "@/app/providers/ThemeProvider";
import type { Stroke } from "@/features/drawing/types";

/**
 * The class's drawing step.
 *
 * The teacher has explained a letter and now asks the child to make it. What
 * happens here is **not marked**: the accuracy is scored on the device, in
 * deterministic code, purely so the app knows when to say "that is it" - no
 * attempt is written, no star moves, and a child who cannot manage the shape is
 * never held here. Tracing is a two-year-old's hand, and hand control is not
 * the thing the level is teaching.
 *
 * A concept with no authored geometry is not drawn as something approximate: it
 * says so and offers the way on, which is the same rule the pictures keep.
 */
export function ClassTrace({
  target: token,
  disabled,
  onDone,
}: {
  /** What to trace, exactly as the server named it. */
  target: string;
  disabled?: boolean;
  /** The child has made it, or has asked to move on. Either way the class goes. */
  onDone: () => void;
}) {
  const theme = useTheme();
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [result, setResult] = useState<ReturnType<typeof scoreTrace> | null>(null);

  const target = useMemo(() => traceTargetFor(token), [token]);
  const scaled = useMemo(() => {
    if (!target || size.width === 0) return null;
    return scaleTarget(target, size);
  }, [target, size]);

  // A new thing to trace starts on a clean canvas.
  useEffect(() => {
    setStrokes([]);
    setResult(null);
  }, [token]);

  const check = useCallback(() => {
    if (!scaled) return;
    const score = scoreTrace(strokes, scaled.samples);
    setResult(score);
    if (score.passed) onDone();
  }, [scaled, strokes, onDone]);

  if (!target) {
    return (
      <Pressable
        accessibilityRole="button"
        onPress={onDone}
        style={{
          minHeight: theme.touchTarget.child,
          justifyContent: "center",
          borderRadius: theme.radius.xl,
          backgroundColor: theme.palette.leaf,
          paddingHorizontal: theme.space[6],
        }}
      >
        <Text variant="subheading" color={theme.palette.white} align="center">
          👍 Let us carry on
        </Text>
      </Pressable>
    );
  }

  return (
    <View style={{ width: "100%", gap: theme.space[2] }}>
      <Text variant="body" align="center" muted>
        Start at the green dot and follow the line.
      </Text>

      <DrawingCanvas
        strokes={strokes}
        onStrokesChange={(next) => {
          setStrokes(next);
          setResult(null);
        }}
        guidePath={scaled?.path}
        startPoint={scaled?.start}
        strokeColor={theme.palette.berry}
        strokeWidth={16}
        height={200}
        disabled={disabled}
        onLayoutSize={setSize}
      />

      {result ? (
        <Text
          variant="label"
          align="center"
          color={result.passed ? theme.colors.success : theme.colors.text}
        >
          {traceFeedback(result)}
        </Text>
      ) : null}

      <View style={{ flexDirection: "row", gap: theme.space[2] }}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Clear the drawing"
          onPress={() => {
            setStrokes([]);
            setResult(null);
          }}
          style={{
            minHeight: theme.touchTarget.parent,
            justifyContent: "center",
            borderRadius: theme.radius.lg,
            backgroundColor: theme.colors.surfaceSunken,
            paddingHorizontal: theme.space[4],
          }}
        >
          <Text variant="label">🧽</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={disabled}
          // Done either way. A trace that did not score well is still a child
          // who drew something, and holding them at a letter they cannot yet
          // form is how a lesson becomes a test of handwriting.
          onPress={() => (strokes.length ? check() : onDone())}
          style={{
            flex: 1,
            minHeight: theme.touchTarget.child,
            justifyContent: "center",
            borderRadius: theme.radius.xl,
            backgroundColor: theme.palette.leaf,
            opacity: disabled ? 0.5 : 1,
          }}
        >
          <Text variant="subheading" color={theme.palette.white} align="center">
            {strokes.length ? "✅ Done!" : "👍 Next"}
          </Text>
        </Pressable>
      </View>

      {/* A child who cannot trace must still get on. */}
      {result && !result.passed ? (
        <Pressable accessibilityRole="button" onPress={onDone} style={{ paddingVertical: theme.space[2] }}>
          <Text variant="body" align="center" muted>
            Carry on
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}
