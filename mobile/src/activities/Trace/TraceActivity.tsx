import { useCallback, useEffect, useMemo, useState } from "react";
import { View } from "react-native";

import { Button } from "@/components/common/Button";
import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { DrawingCanvas } from "@/features/drawing/DrawingCanvas";
import { scaleTarget, traceTargetFor } from "@/features/tracing/tracePaths";
import { scoreTrace, traceFeedback } from "@/features/tracing/strokeScoring";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useResponsive } from "@/components/responsive/useResponsive";
import type { Stroke } from "@/features/drawing/types";
import type { ActivityComponentProps } from "@/activities/types";

/**
 * Letter and shape tracing (spec section 14). Backs `letter_trace` and
 * `shape_trace`.
 *
 * Scoring happens locally and deterministically — see `strokeScoring.ts`.
 * The child's result is reported upward with its accuracy so the lesson
 * can record it, but the AI is only asked to encourage, never to grade.
 */
export function TraceActivity({
  activity,
  onAnswer,
  onContinue,
  isLocked,
  isSubmitting,
  isToddlerMode,
}: ActivityComponentProps) {
  const theme = useTheme();
  const { isTablet, isLandscape } = useResponsive();

  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [result, setResult] = useState<ReturnType<typeof scoreTrace> | null>(null);

  const target = useMemo(
    () => traceTargetFor(activity.concept || activity.correctAnswer || activity.glyph),
    [activity.concept, activity.correctAnswer, activity.glyph],
  );

  const scaled = useMemo(() => {
    if (!target || canvasSize.width === 0) return null;
    return scaleTarget(target, canvasSize);
  }, [target, canvasSize]);

  // A new question resets the canvas.
  useEffect(() => {
    setStrokes([]);
    setResult(null);
  }, [activity.id]);

  const canvasHeight = isLandscape ? 240 : isTablet ? 420 : 320;

  const check = useCallback(() => {
    if (!scaled) return;
    const score = scoreTrace(strokes, scaled.samples);
    setResult(score);

    if (score.passed) {
      // Report the concept as the answer so the lesson advances through
      // the same path a tapped answer would.
      onAnswer(activity.correctAnswer || activity.concept, {
        input: "draw",
        accuracy: score.accuracy,
      });
    }
  }, [scaled, strokes, onAnswer, activity.correctAnswer, activity.concept]);

  // No trace geometry authored for this concept — degrade to a "just
  // practise" card rather than showing an empty canvas.
  if (!target) {
    return (
      <View style={{ gap: theme.space[4], alignItems: "center" }}>
        <Text variant="childPrompt" align="center">
          {activity.glyph || activity.concept}
        </Text>
        <Text variant="body" align="center" muted>
          Let us practise this one together.
        </Text>
        <Button label="Next" icon="➡️" tone="primary" onPress={onContinue} />
      </View>
    );
  }

  return (
    <View style={{ gap: theme.space[4] }}>
      <View style={{ alignItems: "center", gap: theme.space[1] }}>
        <Text variant={isToddlerMode ? "toddlerPrompt" : "childAnswer"}>{target.label}</Text>
        <Text variant="body" muted align="center">
          Start at the green dot and follow the dots.
        </Text>
      </View>

      <GuideHighlight targetId="trace-canvas" kind="canvas" label={`Tracing area for ${target.label}`}>
        <DrawingCanvas
          strokes={strokes}
          onStrokesChange={(next) => {
            setStrokes(next);
            setResult(null);
          }}
          guidePath={scaled?.path}
          startPoint={scaled?.start}
          strokeColor={theme.palette.berry}
          strokeWidth={isToddlerMode ? 18 : 14}
          height={canvasHeight}
          disabled={isLocked || isSubmitting}
          onLayoutSize={setCanvasSize}
        />
      </GuideHighlight>

      {result ? (
        <Text
          variant="subheading"
          align="center"
          color={result.passed ? theme.colors.success : theme.colors.text}
        >
          {traceFeedback(result)}
        </Text>
      ) : null}

      <View style={{ flexDirection: "row", gap: theme.space[3] }}>
        <View style={{ flex: 1 }}>
          <Button
            label="Clear"
            icon="🧽"
            tone="quiet"
            onPress={() => {
              setStrokes([]);
              setResult(null);
            }}
          />
        </View>
        <View style={{ flex: 2 }}>
          <Button
            label={result && !result.passed ? "Try again" : "Done!"}
            icon="✅"
            tone="primary"
            disabled={strokes.length === 0 || isSubmitting}
            onPress={check}
          />
        </View>
      </View>

      {/* Escape hatch: a child who cannot trace must still progress. */}
      {result && !result.passed ? (
        <Button label="Skip this one" tone="quiet" onPress={onContinue} />
      ) : null}
    </View>
  );
}
