import { useEffect, useId } from "react";
import { View, type ViewStyle } from "react-native";
import Svg, {
  Circle,
  ClipPath,
  Defs,
  Ellipse,
  G,
  Path,
  RadialGradient,
  Rect,
  Stop,
} from "react-native-svg";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { useTheme } from "@/app/providers/ThemeProvider";
import type { AvatarState } from "@/types/domain";

/**
 * The panda, drawn - the same panda the web class has, in `react-native-svg`.
 *
 * It is one viewBox'd drawing rather than a stack of positioned views, so every
 * feature keeps its proportion from a 56pt dock to a full-screen stage. The
 * older `AvatarFace` here was built out of RN views with offsets in points, and
 * at stage size those offsets put the ears in the corners.
 *
 * What the face is doing is a **table**, not a stylesheet. On the web each
 * feeling is a CSS class that shows one mouth and one pair of brows; there is
 * no cascade to lean on here, so `FACES` below says the same thing in data and
 * the drawing reads it. Keeping it as one table is also what makes the rule
 * checkable at a glance: fifteen feelings, one mouth each, and never two mouths
 * on the face at once.
 *
 * The `holding` pose is a single transform on `panda-upper` - head lifted and
 * smaller, arms round the front, a board in its paws - which is why all fifteen
 * feelings keep working inside it untouched.
 */

type Mouth = "closed" | "soft" | "grin" | "oh" | "frown" | "cry";
type Eyes = "open" | "joy" | "shut" | "sleepy";
type Brows = "none" | "soft" | "up" | "one" | "sad";

type Face = {
  eyes: Eyes;
  brows: Brows;
  mouth: Mouth;
  cheeks: boolean;
  tears: boolean;
  sparkles: boolean;
};

const DEFAULT_FACE: Face = {
  eyes: "open",
  brows: "none",
  mouth: "closed",
  cheeks: false,
  tears: false,
  sparkles: false,
};

/**
 * One row per feeling, and the three the user asked to be able to tell apart
 * across a room are the three that differ most: **right** is `celebrating` -
 * eyes shut in a grin, cheeks up, sparkles; **thinking** is one brow up and a
 * small steady smile; **wrong** is `encouraging`, which is *kind* - concerned
 * brows, a soft smile, warm cheeks - and never sad.
 */
const FACES: Record<AvatarState, Face> = {
  idle: DEFAULT_FACE,
  speaking: DEFAULT_FACE,
  storytelling: DEFAULT_FACE,
  waving: { ...DEFAULT_FACE, eyes: "joy", mouth: "grin" },
  happy: { ...DEFAULT_FACE, eyes: "joy", mouth: "grin", cheeks: true },
  celebrating: {
    eyes: "joy",
    brows: "up",
    mouth: "grin",
    cheeks: true,
    tears: false,
    sparkles: true,
  },
  proud: { ...DEFAULT_FACE, eyes: "joy", mouth: "grin", cheeks: true, sparkles: true },
  encouraging: { ...DEFAULT_FACE, brows: "soft", mouth: "soft", cheeks: true },
  thinking: { ...DEFAULT_FACE, brows: "one", mouth: "soft" },
  curious: { ...DEFAULT_FACE, brows: "up", mouth: "oh" },
  listening: { ...DEFAULT_FACE, brows: "up", mouth: "soft" },
  sleeping: { ...DEFAULT_FACE, eyes: "sleepy", mouth: "soft" },
  sad: { ...DEFAULT_FACE, brows: "sad", mouth: "frown" },
  crying: { eyes: "shut", brows: "sad", mouth: "cry", cheeks: true, tears: true, sparkles: false },
  error_fallback: { ...DEFAULT_FACE, brows: "soft", mouth: "frown" },
};

const GLOSS_TOP = "#6d5a52";
const GLOSS_BOTTOM = "#241d19";
const LINE = "#241d19";

export type PandaAvatarProps = {
  state: AvatarState;
  /** The mouth moves while anything is being said, whatever the feeling is. */
  isSpeaking?: boolean;
  /** The class's pose: smaller, higher, and holding a board. */
  holding?: boolean;
  style?: ViewStyle;
};

export function PandaAvatar({
  state,
  isSpeaking = false,
  holding = false,
  style,
}: PandaAvatarProps) {
  const theme = useTheme();
  const face = FACES[state] ?? DEFAULT_FACE;
  const bounce = useSharedValue(0);
  // Two pandas can be on one screen - a stage and a dock - and a duplicated
  // gradient id lets one steal the other's paint.
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const fur = `fur-${uid}`;
  const belly = `belly-${uid}`;
  const gloss = `gloss-${uid}`;
  const screen = `screen-${uid}`;

  // Delight is the one feeling that moves the whole panda. Everything else is
  // said with the face, because a picture that is always bobbing is a picture
  // a child stops seeing.
  useEffect(() => {
    if (theme.reduceMotion || (state !== "celebrating" && state !== "proud")) {
      bounce.value = withTiming(0, { duration: 200 });
      return;
    }
    bounce.value = withRepeat(
      withSequence(
        withTiming(-1, { duration: 320, easing: Easing.out(Easing.quad) }),
        withTiming(0, { duration: 320, easing: Easing.in(Easing.quad) }),
      ),
      -1,
      false,
    );
  }, [state, theme.reduceMotion, bounce]);

  const bouncing = useAnimatedStyle(() => ({
    transform: [{ translateY: bounce.value * 8 }],
  }));

  return (
    <Animated.View
      style={[{ width: "100%", height: "100%" }, bouncing, style]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Svg width="100%" height="100%" viewBox="0 0 200 200">
        <Defs>
          <RadialGradient id={fur} cx="38%" cy="30%" r="78%">
            <Stop offset="0%" stopColor="#ffffff" />
            <Stop offset="62%" stopColor="#f9f6f2" />
            <Stop offset="100%" stopColor="#e3dcd4" />
          </RadialGradient>
          <RadialGradient id={belly} cx="42%" cy="26%" r="80%">
            <Stop offset="0%" stopColor="#ffffff" />
            <Stop offset="100%" stopColor="#e6dfd7" />
          </RadialGradient>
          <RadialGradient id={gloss} cx="50%" cy="34%" r="62%">
            <Stop offset="0%" stopColor={GLOSS_TOP} />
            <Stop offset="100%" stopColor={GLOSS_BOTTOM} />
          </RadialGradient>
          <ClipPath id={screen}>
            <Rect x={30} y={100} width={140} height={84} rx={7} />
          </ClipPath>
        </Defs>

        {/* Everything above the shoulders, in one group. Holding the board is a
            single transform on this: the head's own centre (100, 94) goes to
            (100, 50) at 0.56 scale, which lands the ear tops at y 6 - inside
            the frame - and the chin at y 83, far enough above the board's top
            edge at 92 to leave a band of shoulder showing. Without that band
            the panda was a head resting on a monitor. */}
        <G transform={holding ? "translate(100 50) scale(0.56) translate(-100 -94)" : undefined}>
          {/* Ears first, so the head's edge overlaps them and they read as set
              into the skull rather than stuck on. */}
          <G>
            <Circle cx={50} cy={42} r={27} fill={`url(#${gloss})`} />
            <Circle cx={50} cy={44} r={13} fill="#7d6259" opacity={0.75} />
            <Circle cx={150} cy={42} r={27} fill={`url(#${gloss})`} />
            <Circle cx={150} cy={44} r={13} fill="#7d6259" opacity={0.75} />
          </G>

          {/* Body and arms, behind the head. The arms hang at the panda's sides
              only when its paws are free; holding the board they come round the
              front and are drawn with it. */}
          <G>
            {holding ? null : (
              <>
                <Ellipse
                  cx={60}
                  cy={163}
                  rx={17}
                  ry={24}
                  fill={`url(#${gloss})`}
                  transform="rotate(18 60 163)"
                />
                <Ellipse
                  cx={140}
                  cy={163}
                  rx={17}
                  ry={24}
                  fill={`url(#${gloss})`}
                  transform="rotate(-18 140 163)"
                />
              </>
            )}
            <Ellipse cx={100} cy={170} rx={46} ry={33} fill={`url(#${belly})`} />
            <Ellipse cx={79} cy={191} rx={16} ry={11} fill={`url(#${gloss})`} />
            <Ellipse cx={121} cy={191} rx={16} ry={11} fill={`url(#${gloss})`} />
          </G>

          <G>
            <Ellipse cx={100} cy={94} rx={67} ry={59} fill={`url(#${fur})`} />

            {/* The signature patches: teardrops, tilted in towards the nose. */}
            <Ellipse
              cx={72}
              cy={89}
              rx={19}
              ry={24}
              fill={`url(#${gloss})`}
              transform="rotate(-22 72 89)"
            />
            <Ellipse
              cx={128}
              cy={89}
              rx={19}
              ry={24}
              fill={`url(#${gloss})`}
              transform="rotate(22 128 89)"
            />

            {face.cheeks ? (
              <>
                <Ellipse cx={54} cy={118} rx={13} ry={8} fill="#e87891" opacity={0.42} />
                <Ellipse cx={146} cy={118} rx={13} ry={8} fill="#e87891" opacity={0.42} />
              </>
            ) : null}

            {/* Eyebrows, on the white fur above the patches - a dark brow drawn
                on a black eye patch is invisible. They do most of the emotional
                work: the difference between "I am listening" and "oh dear" is
                two short strokes. */}
            <Brow shape={face.brows} />

            {face.eyes === "open" || face.eyes === "sleepy" ? (
              <G opacity={face.eyes === "sleepy" ? 0.35 : 1}>
                <Circle cx={76} cy={91} r={9.6} fill="#fffdfb" />
                <Circle cx={76.6} cy={91.6} r={6.6} fill={LINE} />
                <Circle cx={74} cy={88.6} r={2.7} fill="#ffffff" />
                <Circle cx={79} cy={94} r={1.3} fill="#ffffff" opacity={0.8} />
                <Circle cx={124} cy={91} r={9.6} fill="#fffdfb" />
                <Circle cx={123.4} cy={91.6} r={6.6} fill={LINE} />
                <Circle cx={121} cy={88.6} r={2.7} fill="#ffffff" />
                <Circle cx={126} cy={94} r={1.3} fill="#ffffff" opacity={0.8} />
              </G>
            ) : null}

            {/* Eyes shut in a smile. White, for the same reason the brows are
                dark: these arcs are drawn *on* the black patch. */}
            {face.eyes === "joy" ? (
              <G stroke="#fffdfb" strokeWidth={3.4} strokeLinecap="round" fill="none">
                <Path d="M64 95 Q76 82 88 95" />
                <Path d="M112 95 Q124 82 136 95" />
              </G>
            ) : null}

            {/* And eyes squeezed shut - the same two arcs the other way up. A
                crying face needs them: round open eyes with tears running out
                of them read as a leak rather than as weeping. */}
            {face.eyes === "shut" ? (
              <G stroke="#fffdfb" strokeWidth={3.4} strokeLinecap="round" fill="none">
                <Path d="M64 88 Q76 100 88 88" />
                <Path d="M112 88 Q124 100 136 88" />
              </G>
            ) : null}

            {/* Muzzle, so the nose sits on something instead of floating. */}
            <Ellipse cx={100} cy={122} rx={27} ry={19} fill="#fffdfa" opacity={0.95} />
            <Path
              d="M100 108c7.4 0 12.4 2.6 12.4 6.4 0 4.2-5.6 8.8-12.4 8.8s-12.4-4.6-12.4-8.8c0-3.8 5-6.4 12.4-6.4z"
              fill={`url(#${gloss})`}
            />
            <Ellipse
              cx={95.4}
              cy={112.4}
              rx={3}
              ry={1.9}
              fill="#ffffff"
              opacity={0.42}
              transform="rotate(-18 95.4 112.4)"
            />
            <Path d="M100 123v6" stroke={LINE} strokeWidth={3} strokeLinecap="round" fill="none" />

            {/* One mouth at a time. The talking mouth replaces the resting one
                rather than joining it, so a new feeling can never leave two
                mouths on the face. */}
            {isSpeaking ? (
              <G>
                <Ellipse cx={100} cy={136} rx={11} ry={9.5} fill="#3a2723" />
                <Ellipse cx={100} cy={140.5} rx={6.6} ry={4.6} fill="#e07f92" />
              </G>
            ) : (
              <Mouth shape={face.mouth} />
            )}

            {/* Tears last of everything on the head, so they run *over* the fur
                and the muzzle rather than under them. */}
            {face.tears ? (
              <G fill="#7fc8ee">
                <Path d="M72 101c3.2 5.4 5.2 8.2 5.2 10.8a5.2 5.2 0 0 1-10.4 0c0-2.6 2-5.4 5.2-10.8z" />
                <Path d="M128 101c3.2 5.4 5.2 8.2 5.2 10.8a5.2 5.2 0 0 1-10.4 0c0-2.6 2-5.4 5.2-10.8z" />
              </G>
            ) : null}
          </G>
        </G>

        {/* The board the panda holds up, and nothing on it.
            The lit face is x 30..170, y 100..184 out of the 200x200 viewBox.
            `TeacherStage` lays the lesson's drawing over exactly those four
            numbers, so the two move together and never on their own. */}
        {holding ? (
          <G>
            {/* Shoulders, and two arms reaching round the board. Both are drawn
                *before* it, so the top of each arm disappears behind it and the
                arm reads as coming from a body rather than being stuck on. */}
            <Ellipse cx={100} cy={116} rx={46} ry={30} fill={`url(#${gloss})`} />
            <Path
              d="M70 92C48 100 30 112 27 130"
              stroke={`url(#${gloss})`}
              strokeWidth={19}
              strokeLinecap="round"
              fill="none"
            />
            <Path
              d="M130 92C152 100 170 112 173 130"
              stroke={`url(#${gloss})`}
              strokeWidth={19}
              strokeLinecap="round"
              fill="none"
            />
            <Rect x={22} y={92} width={156} height={104} rx={13} fill="#25313f" />
            <Rect x={24} y={94} width={152} height={100} rx={11} fill="#33445a" />
            {/* The lit face. Light, because the lesson draws on it in ink. */}
            <Rect x={30} y={100} width={140} height={84} rx={7} fill="#f7fbff" />
            <G clipPath={`url(#${screen})`}>
              <Path d="M30 172 L96 100 L126 100 L30 200z" fill="#ffffff" opacity={0.5} />
            </G>
            <Rect
              x={30}
              y={100}
              width={140}
              height={84}
              rx={7}
              fill="none"
              stroke="#c3d7e4"
              strokeWidth={1.6}
            />
            <Circle cx={100} cy={190} r={2.8} fill="#7ed09a" />
          </G>
        ) : null}
      </Svg>

      {face.sparkles ? <Sparkles /> : null}
    </Animated.View>
  );
}

function Brow({ shape }: { shape: Brows }) {
  if (shape === "none") return null;
  const props = {
    stroke: LINE,
    strokeWidth: 4,
    strokeLinecap: "round" as const,
    fill: "none",
  };
  if (shape === "soft") {
    return (
      <G {...props}>
        <Path d="M58 65 Q72 56 87 58" />
        <Path d="M142 65 Q128 56 113 58" />
      </G>
    );
  }
  if (shape === "up") {
    return (
      <G {...props}>
        <Path d="M58 58 Q72 49 87 55" />
        <Path d="M142 58 Q128 49 113 55" />
      </G>
    );
  }
  if (shape === "one") {
    return (
      <G {...props}>
        <Path d="M58 63 Q72 60 87 63" />
        <Path d="M142 55 Q128 47 113 53" />
      </G>
    );
  }
  // Sorry: the inner ends climb towards the nose and the outer ends drop away.
  // The one brow shape a face cannot fake, and the whole difference between
  // "oh dear" and "I am thinking".
  return (
    <G {...props}>
      <Path d="M57 70 Q71 61 88 54" />
      <Path d="M143 70 Q129 61 112 54" />
    </G>
  );
}

function Mouth({ shape }: { shape: Mouth }) {
  if (shape === "grin") {
    return (
      <G>
        <Path d="M81 127q19 22 38 0z" fill="#3a2723" />
        <Ellipse cx={100} cy={139} rx={7.4} ry={4.6} fill="#e07f92" />
      </G>
    );
  }
  if (shape === "oh") {
    return <Ellipse cx={100} cy={133} rx={6.8} ry={8.4} fill="#3a2723" />;
  }
  if (shape === "cry") {
    // Wailing: wide at the top, tapering, with the tongue showing. A frown
    // alone is disappointment; this is the mouth that goes with the tears.
    return (
      <G>
        <Path d="M85 132q15 -10 30 0q-3 17 -15 17t-15 -17z" fill="#3a2723" />
        <Ellipse cx={100} cy={144} rx={6.4} ry={3.8} fill="#e07f92" />
      </G>
    );
  }
  const line = {
    stroke: LINE,
    strokeWidth: 3.2,
    strokeLinecap: "round" as const,
    fill: "none",
  };
  if (shape === "frown") return <Path d="M89 134q11 -8 22 0" {...line} />;
  if (shape === "soft") return <Path d="M92 130q8 5 16 0" {...line} />;
  return <Path d="M100 129c-3.4 6.6-11.6 6.2-14.4 1.2M100 129c3.4 6.6 11.6 6.2 14.4 1.2" {...line} />;
}

/** Two stars over the top corners, for the two feelings that earn them. */
function Sparkles() {
  return (
    <View
      pointerEvents="none"
      style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
    >
      <View style={{ position: "absolute", top: "6%", left: "8%" }}>
        <SparkleGlyph />
      </View>
      <View style={{ position: "absolute", top: "14%", right: "8%" }}>
        <SparkleGlyph small />
      </View>
    </View>
  );
}

function SparkleGlyph({ small = false }: { small?: boolean }) {
  const theme = useTheme();
  const shine = useSharedValue(0.4);

  useEffect(() => {
    if (theme.reduceMotion) return;
    shine.value = withRepeat(
      withSequence(withTiming(1, { duration: 750 }), withTiming(0.4, { duration: 750 })),
      -1,
      false,
    );
  }, [shine, theme.reduceMotion]);

  const twinkle = useAnimatedStyle(() => ({ opacity: shine.value }));
  const size = small ? 16 : 22;

  return (
    <Animated.View style={twinkle}>
      <Svg width={size} height={size} viewBox="0 0 24 24">
        <Path
          d="M12 1.5 L14.4 9 L22 12 L14.4 15 L12 22.5 L9.6 15 L2 12 L9.6 9 Z"
          fill="#f5b84b"
        />
      </Svg>
    </Animated.View>
  );
}

/**
 * The two paws that close over the board, on their own layer.
 *
 * They are not part of the panda's SVG because of the order things have to be
 * painted in: board, then the lesson's drawing, then the paws. A paw *behind*
 * the thing it is holding is not a panda holding a board - it is a panda
 * standing near one - and the drawing has to sit between the two.
 */
export function PandaPaws() {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const paw = `paw-${uid}`;
  return (
    <View
      pointerEvents="none"
      style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
    >
      <Svg width="100%" height="100%" viewBox="0 0 200 200">
        <Defs>
          <RadialGradient id={paw} cx="50%" cy="34%" r="62%">
            <Stop offset="0%" stopColor={GLOSS_TOP} />
            <Stop offset="100%" stopColor={GLOSS_BOTTOM} />
          </RadialGradient>
        </Defs>
        {/* Each hand is a mitten with three toes down its inner edge, and it
            overlaps the board's edge by a few units - a paw that stops short of
            the thing it is holding is a panda standing next to a board. */}
        <G transform="rotate(12 27 140)">
          <Ellipse cx={27} cy={140} rx={12.5} ry={16.5} fill={`url(#${paw})`} />
          <Circle cx={35} cy={129} r={3} fill="#7d6259" opacity={0.85} />
          <Circle cx={37} cy={139} r={3.2} fill="#7d6259" opacity={0.85} />
          <Circle cx={35} cy={149} r={3} fill="#7d6259" opacity={0.85} />
        </G>
        <G transform="rotate(-12 173 140)">
          <Ellipse cx={173} cy={140} rx={12.5} ry={16.5} fill={`url(#${paw})`} />
          <Circle cx={165} cy={129} r={3} fill="#7d6259" opacity={0.85} />
          <Circle cx={163} cy={139} r={3.2} fill="#7d6259" opacity={0.85} />
          <Circle cx={165} cy={149} r={3} fill="#7d6259" opacity={0.85} />
        </G>
      </Svg>
    </View>
  );
}
