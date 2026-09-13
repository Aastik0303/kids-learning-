import { useEffect, useMemo } from "react";
import { View, type ViewStyle } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";
import Animated, {
  useAnimatedProps,
  useSharedValue,
  withDelay,
  withTiming,
  Easing,
} from "react-native-reanimated";

import { useTheme } from "@/app/providers/ThemeProvider";
import { measurePath, viewBoxFor } from "@/components/blackboard/pathGeometry";
import type { ChalkArt, ChalkStroke } from "@/components/blackboard/chalkArt";

const AnimatedPath = Animated.createAnimatedComponent(Path);
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

/**
 * A drawing that draws itself, the way a teacher's hand does.
 *
 * The point is timing and nothing else. A finished picture that appears the
 * instant the narration starts has been looked at and left before the words
 * reach it; a line that is still arriving is a line a two-year-old will watch
 * for as long as it takes to arrive. So every stroke is revealed along its own
 * length - the dash array set to the length and the offset walked down to zero
 * - and the strokes are walked in the order the artwork lists them, so the
 * child sees the outline of the apple made before the stalk is put on it.
 *
 * Each stroke takes a share of the time proportional to how long it is, which
 * is why the geometry is measured rather than guessed: an even split makes a
 * stalk take as long as the fruit it is on.
 *
 * Two differences from the web build, both forced by the platform and neither
 * of them a change of intent. There is no chalk tip riding the moving end,
 * because that needs a point along the path and `react-native-svg` cannot give
 * one. And the walk runs on the UI thread through Reanimated rather than on a
 * frame loop writing to the DOM - which is the same decision the web made for
 * the same reason: a five-stroke drawing at 60fps must not be 300 React
 * renders a second on a screen that is also holding a microphone open.
 *
 * A child whose device asks for less motion gets the finished drawing at once.
 */

export type ChalkDrawingProps = {
  strokes: ChalkArt;
  /**
   * What it is drawn with. `ink` is a dark line for a light board - which is
   * what the panda holds - and `chalk` is the white line a dark slate needs.
   */
  tone?: "ink" | "chalk";
  /** Changing this wipes the board and draws again from nothing. */
  playKey: string;
  /** How long the whole drawing takes, once it starts. */
  durationMs?: number;
  /** How long the board stays blank first, so drawings can follow each other. */
  delayMs?: number;
  /** What the drawing is, for a screen reader. */
  label: string;
  style?: ViewStyle;
};

const CHALK = "#f6f8f3";
const INK = "#25313f";

/** How strongly a colour reads. Pastel washes vanish on white. */
const WASH = { ink: 0.72, chalk: 0.42 } as const;

/** Where a `dot` stroke sits - the first coordinate pair in its `d`. */
function dotAt(d: string): { cx: number; cy: number } {
  const found = d.match(/-?\d+(?:\.\d+)?/g);
  return { cx: Number(found?.[0] ?? 50), cy: Number(found?.[1] ?? 50) };
}

type Timed = {
  stroke: ChalkStroke;
  length: number;
  /** When this stroke starts and how long it takes, in milliseconds. */
  startMs: number;
  runMs: number;
};

/**
 * One walked line, plus the colour washed inside it once it is closed.
 *
 * The wash arrives *after* the outline rather than with it, because a shape
 * that fills as it is drawn looks like a spill rather than like colouring in.
 */
function Stroke({
  timed,
  line,
  tone,
  still,
}: {
  timed: Timed;
  line: string;
  tone: "ink" | "chalk";
  still: boolean;
}) {
  const { stroke, length, startMs, runMs } = timed;
  // Starts hidden - the whole line pushed out of view by its own length - and
  // is walked to zero. A stroke with no measurable length is simply shown.
  const offset = useSharedValue(still || length <= 0 ? 0 : length);
  const wash = useSharedValue(still ? 1 : 0);

  useEffect(() => {
    if (still || length <= 0) {
      offset.value = 0;
      wash.value = 1;
      return;
    }
    offset.value = length;
    wash.value = 0;
    offset.value = withDelay(
      startMs,
      withTiming(0, { duration: runMs, easing: Easing.inOut(Easing.quad) }),
    );
    wash.value = withDelay(startMs + runMs * 0.6, withTiming(1, { duration: 420 }));
    // The walk is re-armed for a new turn, never on every render: `playKey` is
    // what the parent changes when the board should be wiped, and it remounts
    // this component, so the values above start from scratch on their own.
  }, [length, startMs, runMs, still, offset, wash]);

  const lineProps = useAnimatedProps(() => ({ strokeDashoffset: offset.value }));
  const washProps = useAnimatedProps(() => ({ opacity: wash.value }));

  return (
    <>
      {stroke.fill ? (
        <AnimatedPath
          d={stroke.d}
          fill={stroke.fill}
          fillOpacity={stroke.fillOpacity ?? WASH[tone]}
          stroke="none"
          animatedProps={washProps}
        />
      ) : null}
      <AnimatedPath
        d={stroke.d}
        fill="none"
        stroke={stroke.stroke ?? line}
        strokeWidth={stroke.width ?? 3.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={length > 0 ? [length, length] : undefined}
        animatedProps={lineProps}
      />
    </>
  );
}

/** An eye, a seed, a full stop: put down whole rather than walked. */
function Dot({
  timed,
  line,
  still,
}: {
  timed: Timed;
  line: string;
  still: boolean;
}) {
  const shown = useSharedValue(still ? 1 : 0);
  const { cx, cy } = dotAt(timed.stroke.d);

  useEffect(() => {
    if (still) {
      shown.value = 1;
      return;
    }
    shown.value = 0;
    shown.value = withDelay(timed.startMs, withTiming(1, { duration: 220 }));
  }, [timed.startMs, still, shown]);

  const props = useAnimatedProps(() => ({ opacity: shown.value }));

  return (
    <AnimatedCircle
      cx={cx}
      cy={cy}
      r={timed.stroke.width ?? 3}
      fill={timed.stroke.stroke ?? line}
      animatedProps={props}
    />
  );
}

export function ChalkDrawing({
  strokes,
  playKey,
  tone = "ink",
  durationMs = 2200,
  delayMs = 0,
  label,
  style,
}: ChalkDrawingProps) {
  const theme = useTheme();
  const line = tone === "chalk" ? CHALK : INK;

  const { timed, viewBox } = useMemo(() => {
    const lengths = strokes.map((stroke) => (stroke.dot ? 0 : measurePath(stroke.d).length));
    const total = lengths.reduce((sum, one) => sum + one, 0);
    let spent = 0;
    const plan: Timed[] = strokes.map((stroke, index) => {
      const length = lengths[index] ?? 0;
      // A drawing of nothing but dots has no length to share out, so they are
      // spread evenly instead of all landing on the first frame.
      const share = total > 0 ? length / total : 1 / Math.max(1, strokes.length);
      const startMs = delayMs + (total > 0 ? (spent / total) * durationMs : index * (durationMs / Math.max(1, strokes.length)));
      spent += length;
      return { stroke, length, startMs, runMs: Math.max(140, share * durationMs) };
    });
    return {
      timed: plan,
      viewBox: viewBoxFor(strokes.map((stroke) => ({ d: stroke.d, width: stroke.width }))),
    };
  }, [strokes, durationMs, delayMs]);

  return (
    <View
      style={[{ flex: 1, width: "100%" }, style]}
      accessibilityRole="image"
      accessibilityLabel={label}
    >
      <Svg key={playKey} width="100%" height="100%" viewBox={viewBox}>
        {timed.map((one, index) =>
          one.stroke.dot ? (
            <Dot key={`${playKey}-${index}`} timed={one} line={line} still={theme.reduceMotion} />
          ) : (
            <Stroke
              key={`${playKey}-${index}`}
              timed={one}
              line={line}
              tone={tone}
              still={theme.reduceMotion}
            />
          ),
        )}
      </Svg>
    </View>
  );
}
