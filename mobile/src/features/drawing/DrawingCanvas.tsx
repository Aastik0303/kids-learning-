import { useCallback, useMemo, useRef, useState } from "react";
import { PanResponder, View, type LayoutChangeEvent, type ViewStyle } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";

import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";
import { toSvgPath, type Point, type Stroke } from "@/features/drawing/types";

export type DrawingCanvasProps = {
  /** Committed strokes. The canvas is controlled — the parent owns these. */
  strokes: Stroke[];
  onStrokesChange: (strokes: Stroke[]) => void;

  /** Faint dashed path the child follows. Omit for free drawing. */
  guidePath?: string;
  /** Where the stroke should begin, drawn as a green dot. */
  startPoint?: Point;
  strokeColor?: string;
  strokeWidth?: number;
  height?: number;
  style?: ViewStyle;
  disabled?: boolean;
  /** Reports the measured drawing area so paths can be scaled to it. */
  onLayoutSize?: (size: { width: number; height: number }) => void;
};

/**
 * The shared surface behind letter tracing, shape tracing and free draw.
 *
 * Built on PanResponder rather than Reanimated worklets deliberately:
 * stroke capture must never drop a point, and the plain JS path has fewer
 * failure modes across the New Architecture. Points are distance-filtered
 * so a slow child finger does not generate thousands of near-identical
 * samples.
 *
 * Controlled by design — tracing screens need to score, clear and undo
 * strokes, so the parent holds them.
 */
export function DrawingCanvas({
  strokes,
  onStrokesChange,
  guidePath,
  startPoint,
  strokeColor,
  strokeWidth = 14,
  height = 300,
  style,
  disabled = false,
  onLayoutSize,
}: DrawingCanvasProps) {
  const theme = useTheme();
  const [size, setSize] = useState({ width: 0, height });
  const [current, setCurrent] = useState<Point[]>([]);

  // Live buffer — responder callbacks are not React-scheduled, so the
  // authoritative point list lives in a ref and state only mirrors it.
  const buffer = useRef<Point[]>([]);
  const strokeCounter = useRef(0);

  // Kept in a ref so the PanResponder closure never goes stale.
  const strokesRef = useRef(strokes);
  strokesRef.current = strokes;

  const color = strokeColor ?? theme.palette.berry;

  const commitStroke = useCallback(() => {
    if (buffer.current.length < 2) {
      buffer.current = [];
      setCurrent([]);
      return;
    }
    strokeCounter.current += 1;
    const stroke: Stroke = {
      id: `s${strokeCounter.current}-${Date.now()}`,
      points: buffer.current,
      color,
      width: strokeWidth,
    };
    buffer.current = [];
    setCurrent([]);
    onStrokesChange([...strokesRef.current, stroke]);
    haptics.strokeComplete();
  }, [color, strokeWidth, onStrokesChange]);

  const responder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => !disabled,
        onMoveShouldSetPanResponder: () => !disabled,
        // Claim the gesture so a parent ScrollView cannot steal the stroke.
        onPanResponderTerminationRequest: () => false,

        onPanResponderGrant: (event) => {
          const { locationX, locationY } = event.nativeEvent;
          buffer.current = [{ x: locationX, y: locationY }];
          setCurrent(buffer.current);
        },

        onPanResponderMove: (event) => {
          const { locationX, locationY } = event.nativeEvent;
          const last = buffer.current[buffer.current.length - 1];
          // Drop samples closer than 2pt — pure noise at this scale.
          if (last && Math.hypot(locationX - last.x, locationY - last.y) < 2) return;
          buffer.current = [...buffer.current, { x: locationX, y: locationY }];
          setCurrent(buffer.current);
        },

        onPanResponderRelease: commitStroke,
        onPanResponderTerminate: commitStroke,
      }),
    [disabled, commitStroke],
  );

  return (
    <View
      accessibilityLabel="Drawing area"
      onLayout={(event: LayoutChangeEvent) => {
        const { width, height: measured } = event.nativeEvent.layout;
        setSize({ width, height: measured });
        onLayoutSize?.({ width, height: measured });
      }}
      style={[
        {
          height,
          borderRadius: theme.radius.card,
          borderWidth: 3,
          borderColor: theme.colors.border,
          backgroundColor: theme.colors.surface,
          overflow: "hidden",
        },
        style,
      ]}
      {...responder.panHandlers}
    >
      <Svg width="100%" height="100%" viewBox={`0 0 ${size.width || 1} ${size.height || 1}`}>
        {/* Guide path sits underneath, dashed and faint. */}
        {guidePath ? (
          <Path
            d={guidePath}
            stroke={theme.inkAlpha.a25}
            strokeWidth={strokeWidth + 8}
            strokeDasharray="12 14"
            strokeLinecap="round"
            fill="none"
          />
        ) : null}

        {startPoint ? (
          <Circle cx={startPoint.x} cy={startPoint.y} r={14} fill={theme.colors.success} opacity={0.9} />
        ) : null}

        {strokes.map((stroke) => (
          <Path
            key={stroke.id}
            d={toSvgPath(stroke.points)}
            stroke={stroke.color}
            strokeWidth={stroke.width}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        ))}

        {current.length > 1 ? (
          <Path
            d={toSvgPath(current)}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        ) : null}
      </Svg>
    </View>
  );
}
