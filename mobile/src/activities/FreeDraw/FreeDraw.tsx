import { useEffect, useState } from "react";
import { Pressable, View } from "react-native";

import { Button } from "@/components/common/Button";
import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { DrawingCanvas } from "@/features/drawing/DrawingCanvas";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useResponsive } from "@/components/responsive/useResponsive";
import { haptics } from "@/services/audio/haptics";
import type { Stroke } from "@/features/drawing/types";
import type { ActivityComponentProps } from "@/activities/types";

/**
 * Open drawing. There is no right answer here by design — the activity
 * completes when the child says they are done.
 *
 * The guide encourages and can talk about what was drawn, but nothing
 * scores it. "Draw a happy sun" has no wrong outcome.
 */
export function FreeDraw({ activity, onContinue, isLocked, isToddlerMode }: ActivityComponentProps) {
  const theme = useTheme();
  const { isTablet, isLandscape } = useResponsive();

  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [color, setColor] = useState<string>(theme.palette.berry);

  useEffect(() => {
    setStrokes([]);
  }, [activity.id]);

  const palette = [
    theme.palette.berry,
    theme.palette.sky,
    theme.palette.leaf,
    theme.palette.sunshine,
    theme.palette.lavender,
    theme.palette.ink,
  ];

  const canvasHeight = isLandscape ? 260 : isTablet ? 460 : 340;

  return (
    <View style={{ gap: theme.space[4] }}>
      <GuideHighlight targetId="draw-canvas" kind="canvas" label="Drawing area">
        <DrawingCanvas
          strokes={strokes}
          onStrokesChange={setStrokes}
          strokeColor={color}
          strokeWidth={isToddlerMode ? 20 : 15}
          height={canvasHeight}
          disabled={isLocked}
        />
      </GuideHighlight>

      {/* Colour picker */}
      <View style={{ flexDirection: "row", justifyContent: "center", gap: theme.space[3] }}>
        {palette.map((swatch) => (
          <Pressable
            key={swatch}
            accessibilityRole="button"
            accessibilityLabel={`Pick colour ${swatch}`}
            accessibilityState={{ selected: swatch === color }}
            onPress={() => {
              haptics.tap();
              setColor(swatch);
            }}
            style={{
              width: isToddlerMode ? 56 : 46,
              height: isToddlerMode ? 56 : 46,
              borderRadius: 999,
              backgroundColor: swatch,
              borderWidth: swatch === color ? 5 : 2,
              borderColor: swatch === color ? theme.colors.accent : theme.colors.border,
              ...theme.shadows.soft,
            }}
          />
        ))}
      </View>

      <View style={{ flexDirection: "row", gap: theme.space[3] }}>
        <View style={{ flex: 1 }}>
          <Button
            label="Undo"
            icon="↩️"
            tone="quiet"
            disabled={strokes.length === 0}
            onPress={() => setStrokes((current) => current.slice(0, -1))}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Button
            label="Clear"
            icon="🧽"
            tone="quiet"
            disabled={strokes.length === 0}
            onPress={() => setStrokes([])}
          />
        </View>
      </View>

      <Button label="I am done!" icon="🎉" tone="primary" onPress={onContinue} />

      {strokes.length === 0 ? (
        <Text variant="body" align="center" muted>
          Use your finger to draw.
        </Text>
      ) : null}
    </View>
  );
}
