import { useEffect, useMemo } from "react";
import { Platform, View, type ViewStyle } from "react-native";
import Svg, { Circle, ClipPath, Defs, G, Rect, Text as SvgText } from "react-native-svg";
import Animated, {
  useAnimatedProps,
  useSharedValue,
  withDelay,
  withTiming,
  Easing,
} from "react-native-reanimated";

import { useTheme } from "@/app/providers/ThemeProvider";

const AnimatedRect = Animated.createAnimatedComponent(Rect);
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

/**
 * A letter, a numeral or a word, written onto the board rather than printed on
 * it.
 *
 * The other drawings are walked along a path, which is only possible because
 * their outlines are hand-written coordinates. A glyph has no path to walk: "A"
 * is whatever shape the font makes of it, and क is a shape no rule here knows.
 * So the writing is done as a wipe - revealed left to right, with a chalk tip
 * at the edge - which is close enough to a hand for a child to watch, works for
 * every script the syllabus uses, and cannot get a letter's stroke order wrong
 * by guessing at it.
 *
 * The letter *is* the lesson, so it is written in whatever font can render it.
 * A Devanagari letter must never come out as an empty box, which is why the
 * family below names the platform's own Indic face before anything else.
 */

export type ChalkGlyphProps = {
  text: string;
  /** Changing this wipes the board and writes it again. */
  playKey: string;
  durationMs?: number;
  delayMs?: number;
  /** The chalk to write in. Colour lessons write in their own colour. */
  colour?: string;
  label?: string;
  style?: ViewStyle;
};

const INK = "#25313f";

/**
 * A hand-written face where there is one, and a face that can carry Devanagari
 * everywhere else. Android resolves Indic through its system fallback, and iOS
 * has Devanagari Sangam MN, so naming a family that cannot render a letter is
 * the one thing that would show a child an empty box.
 */
const GLYPH_FONT = Platform.select({
  ios: "Bradley Hand",
  android: "sans-serif",
  default: "System",
});

function sizeFor(text: string): number {
  // Counted in code points, not UTF-16 units: अं is one letter written with two
  // of them, and sizing it as two would shrink a single Hindi letter by a fifth.
  const length = Array.from(text.trim()).length;
  if (length <= 1) return 88;
  if (length === 2) return 66;
  if (length === 3) return 50;
  return Math.max(18, Math.round(155 / length));
}

export function ChalkGlyph({
  text,
  playKey,
  durationMs = 1500,
  delayMs = 0,
  colour = INK,
  label,
  style,
}: ChalkGlyphProps) {
  const theme = useTheme();
  const still = theme.reduceMotion;
  // How much of the letter has been written, 0..100. The clip pane's width and
  // the chalk tip's position are the same number seen twice.
  const edge = useSharedValue(still ? 100 : 0);

  useEffect(() => {
    if (still) {
      edge.value = 100;
      return;
    }
    edge.value = 0;
    edge.value = withDelay(
      delayMs,
      withTiming(100, { duration: durationMs, easing: Easing.inOut(Easing.quad) }),
    );
  }, [playKey, durationMs, delayMs, still, edge]);

  const paneProps = useAnimatedProps(() => ({ width: edge.value }));
  const tipProps = useAnimatedProps(() => ({
    cx: edge.value,
    // A little up and down, because a hand writing a letter does not travel in
    // a straight line across the board.
    cy: 56 - Math.sin((edge.value / 100) * Math.PI * 3) * 14,
    opacity: edge.value >= 100 ? 0 : 1,
  }));

  const size = useMemo(() => sizeFor(text), [text]);
  /**
   * Where the baseline goes so the letter sits in the middle of the box.
   *
   * `react-native-svg` does not honour `dominantBaseline` on both platforms, so
   * the centring is arithmetic rather than a property: a baseline is roughly
   * 35% of the font size below the visual middle of a capital, and a letter
   * hung off an uncentred baseline sat low enough on the board to be clipped.
   */
  const baseline = 50 + size * 0.35;
  const clipId = `chalk-glyph-${playKey.replace(/[^a-zA-Z0-9-]/g, "")}`;

  return (
    <View
      style={[{ flex: 1, width: "100%" }, style]}
      accessibilityRole="image"
      accessibilityLabel={label ?? text}
    >
      <Svg key={playKey} width="100%" height="100%" viewBox="0 0 100 100">
        <Defs>
          <ClipPath id={clipId}>
            <AnimatedRect x={0} y={0} height={100} animatedProps={paneProps} />
          </ClipPath>
        </Defs>
        <G clipPath={`url(#${clipId})`}>
          {/* The letter twice: a pale wash inside, and the written line over
              it. One alone is either a silhouette or a hollow outline, and a
              child learning the shape needs the line. */}
          <SvgText
            x={50}
            y={baseline}
            textAnchor="middle"
            fontSize={size}
            fontWeight="700"
            fontFamily={GLYPH_FONT}
            fill={colour}
            fillOpacity={0.25}
          >
            {text}
          </SvgText>
          <SvgText
            x={50}
            y={baseline}
            textAnchor="middle"
            fontSize={size}
            fontWeight="700"
            fontFamily={GLYPH_FONT}
            fill="none"
            stroke={colour}
            strokeWidth={1.6}
            strokeLinejoin="round"
          >
            {text}
          </SvgText>
        </G>
        <AnimatedCircle cy={56} r={2.4} fill={colour} animatedProps={tipProps} />
      </Svg>
    </View>
  );
}
