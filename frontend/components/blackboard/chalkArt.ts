/**
 * Line art the blackboard can draw, one chalk stroke at a time.
 *
 * A picture that is simply *there* when the turn loads is a picture the child
 * has already stopped looking at by the time the teacher gets to it. A picture
 * that appears stroke by stroke while the teacher talks is what a real
 * classroom board does, and a two-year-old will watch a line being drawn for
 * as long as it takes to draw it.
 *
 * So every drawing here is a list of `d` strings in the order a hand would make
 * them - outline first, then the details, then the eye - inside a 100x100 box.
 * `ChalkDrawing` walks that list and reveals each path along its own length,
 * which is why they are paths and not `<circle>` / `<rect>`: only a path has a
 * length to walk.
 *
 * Nothing here is generated. These are hand-written coordinates for the tokens
 * the syllabus actually names, and a token with no drawing gets no drawing -
 * the caller falls back to the emoji rather than to a near-miss, which is the
 * same rule `visualIcon` keeps for अनार.
 */

export type ChalkStroke = {
  /** The line to walk, in a 0..100 box. */
  d: string;
  /**
   * Coloured chalk washed inside the shape once its outline has been drawn.
   * Left off for anything whose colour is not part of what it is.
   */
  fill?: string;
  /** Overrides plain white chalk for the line itself. */
  stroke?: string;
  /** How strong the wash is. A colour lesson wants its own colour, not a hint. */
  fillOpacity?: number;
  width?: number;
  /** Drawn as a solid mark rather than walked - an eye, a seed, a full stop. */
  dot?: boolean;
};

export type ChalkArt = ChalkStroke[];

/**
 * A circle as a path, because a walked line needs a length - `<circle>` has no
 * `getTotalLength`, so a ring drawn as one could never be drawn *slowly*.
 */
export function chalkRing(cx: number, cy: number, r: number): string {
  return `M ${cx} ${cy - r} A ${r} ${r} 0 1 1 ${cx - 0.01} ${cy - r} Z`;
}

const RED = "#ef8a85";
const GREEN = "#8fd6a5";
const YELLOW = "#f4d477";
const BROWN = "#c69c72";
const BLUE = "#8ec5ea";
const ORANGE = "#f2ab6d";
const PINK = "#f0a0c0";
const GREY = "#c9d4d0";

const ART: Record<string, ChalkArt> = {
  apple: [
    {
      d: "M50 32 C 30 30 20 50 28 68 C 34 82 46 88 50 82 C 54 88 66 82 72 68 C 80 50 70 30 50 32 Z",
      fill: RED
    },
    { d: "M50 32 C 50 22 52 16 58 11" },
    { d: "M58 15 C 68 8 78 14 75 22 C 70 28 60 25 58 15 Z", fill: GREEN }
  ],
  ball: [
    { d: chalkRing(50, 52, 32) },
    { d: "M22 40 C 40 50 60 50 78 40" },
    { d: "M50 20 C 40 40 40 64 50 84" }
  ],
  banana: [
    {
      d: "M22 40 C 24 68 48 84 72 72 C 79 68 80 61 75 60 C 55 68 38 56 33 38 C 31 31 24 33 22 40 Z",
      fill: YELLOW
    },
    { d: "M33 40 C 38 58 54 68 72 64" }
  ],
  mango: [
    {
      d: "M52 22 C 30 24 20 46 27 63 C 34 80 56 84 68 72 C 82 58 74 24 52 22 Z",
      fill: ORANGE
    },
    { d: "M52 22 C 52 14 56 10 62 9" }
  ],
  sun: [
    { d: chalkRing(50, 50, 22), fill: YELLOW },
    { d: "M50 20 L50 6" },
    { d: "M50 80 L50 94" },
    { d: "M20 50 L6 50" },
    { d: "M80 50 L94 50" },
    { d: "M29 29 L18 18" },
    { d: "M71 29 L82 18" },
    { d: "M29 71 L18 82" },
    { d: "M71 71 L82 82" }
  ],
  // The second arc is the wider one and turns back the other way. An inner arc
  // whose radius is smaller than half the chord cannot exist, so SVG quietly
  // grows it to fit - which turns a crescent into a full circle.
  moon: [{ d: "M58 8 A 44 44 0 1 0 58 92 A 58 58 0 0 1 58 8 Z", fill: YELLOW }],
  star: [
    {
      d: "M50 10 L61 38 L91 38 L67 56 L76 86 L50 68 L24 86 L33 56 L9 38 L39 38 Z",
      fill: YELLOW
    }
  ],
  cloud: [
    {
      d: "M30 70 C 16 70 14 52 29 50 C 29 32 55 28 60 44 C 74 37 87 50 80 61 C 88 63 86 70 77 70 Z",
      fill: GREY
    }
  ],
  rain: [
    {
      d: "M30 56 C 17 56 15 39 30 37 C 30 20 55 17 60 32 C 73 25 86 38 79 48 C 86 50 84 56 76 56 Z",
      fill: GREY
    },
    { d: "M34 64 L30 78", stroke: BLUE },
    { d: "M50 64 L46 78", stroke: BLUE },
    { d: "M66 64 L62 78", stroke: BLUE }
  ],
  tree: [
    { d: "M44 88 L44 60 M56 88 L56 60", stroke: BROWN, width: 5 },
    { d: chalkRing(50, 40, 28), fill: GREEN },
    { d: "M30 52 C 40 44 44 36 46 26" },
    { d: "M70 50 C 60 44 56 36 55 28" }
  ],
  leaf: [
    { d: "M26 74 C 28 40 54 20 78 22 C 80 46 60 74 26 74 Z", fill: GREEN },
    { d: "M28 72 C 46 56 62 42 76 26" },
    { d: "M42 62 L38 48 M56 50 L52 36" }
  ],
  flower: [
    { d: chalkRing(50, 26, 13), fill: PINK },
    { d: chalkRing(73, 43, 13), fill: PINK },
    { d: chalkRing(64, 70, 13), fill: PINK },
    { d: chalkRing(36, 70, 13), fill: PINK },
    { d: chalkRing(27, 43, 13), fill: PINK },
    { d: chalkRing(50, 48, 11), fill: YELLOW }
  ],
  house: [
    { d: "M26 88 L26 48 L74 48 L74 88 Z" },
    { d: "M18 50 L50 24 L82 50", stroke: RED },
    { d: "M42 88 L42 64 L58 64 L58 88" },
    { d: "M31 58 L39 58 L39 66 L31 66 Z", fill: YELLOW }
  ],
  fish: [
    { d: "M22 50 C 34 30 62 30 74 50 C 62 70 34 70 22 50 Z", fill: BLUE },
    { d: "M74 50 L90 36 L90 64 Z" },
    { d: "M60 44 L60 44", dot: true },
    { d: "M46 34 C 50 42 50 58 46 66" }
  ],
  cat: [
    { d: chalkRing(50, 54, 28) },
    { d: "M28 36 L24 14 L44 26" },
    { d: "M72 36 L76 14 L56 26" },
    { d: "M41 50 L41 50", dot: true },
    { d: "M59 50 L59 50", dot: true },
    { d: "M50 60 L46 64 L54 64 Z" },
    { d: "M22 60 L40 62 M22 70 L40 66 M78 60 L60 62 M78 70 L60 66" }
  ],
  dog: [
    { d: chalkRing(50, 54, 26) },
    { d: "M27 36 C 16 40 16 62 28 66", fill: BROWN },
    { d: "M73 36 C 84 40 84 62 72 66", fill: BROWN },
    { d: "M41 50 L41 50", dot: true },
    { d: "M59 50 L59 50", dot: true },
    { d: chalkRing(50, 62, 5), fill: "#8a6a55" },
    { d: "M50 67 L50 74 M50 74 C 46 78 42 76 42 73 M50 74 C 54 78 58 76 58 73" }
  ],
  bird: [
    { d: "M26 58 C 30 38 56 32 70 44 C 79 51 76 63 62 67 C 47 71 30 69 26 58 Z", fill: YELLOW },
    { d: "M70 44 L86 40 L72 52" },
    { d: "M44 52 C 53 46 63 48 66 57" },
    { d: "M66 42 L66 42", dot: true },
    { d: "M26 58 L12 66 L28 66" }
  ],
  egg: [{ d: "M50 18 C 31 20 23 46 30 63 C 37 80 63 80 70 63 C 77 46 69 20 50 18 Z" }],
  // The three below back the shape lessons: a slice of bread and a box are what
  // the teacher says a square is, and a door is what she says a rectangle is.
  // They are drawn rather than left to their emoji because a shape's example
  // has to *look* like the shape beside it.
  bread: [
    { d: "M26 44 C 26 24 42 16 50 16 C 58 16 74 24 74 44 L74 82 L26 82 Z", fill: BROWN },
    { d: "M26 52 L74 52" }
  ],
  box: [
    { d: "M24 40 L76 40 L76 84 L24 84 Z", fill: BROWN },
    { d: "M24 40 L36 24 L88 24 L76 40" },
    { d: "M76 40 L88 24 L88 68 L76 84" },
    { d: "M50 40 L50 84 M24 58 L76 58" }
  ],
  door: [
    { d: "M30 88 L30 14 L70 14 L70 88 Z", fill: BROWN },
    { d: "M36 20 L64 20 L64 46 L36 46 Z" },
    { d: chalkRing(62, 62, 4) }
  ],
  cup: [
    { d: "M28 32 L34 76 C 36 84 64 84 66 76 L72 32 Z" },
    { d: "M70 42 C 86 42 86 66 68 66" },
    { d: "M30 44 L70 44" }
  ],
  boat: [
    { d: "M14 62 L86 62 L72 80 L28 80 Z", fill: BROWN },
    { d: "M50 62 L50 16" },
    { d: "M54 20 L54 58 L80 58 Z", fill: RED },
    { d: "M46 20 L46 58 L24 58 Z" },
    { d: "M8 88 C 20 82 30 92 42 86 C 54 80 64 90 76 84", stroke: BLUE }
  ],
  car: [
    { d: "M12 66 L12 52 L28 52 L38 36 L64 36 L74 52 L88 52 L88 66 Z", fill: BLUE },
    { d: "M40 40 L40 52 M60 40 L60 52" },
    { d: chalkRing(32, 70, 9) },
    { d: chalkRing(70, 70, 9) }
  ],
  bus: [
    { d: "M12 24 L88 24 L88 70 L12 70 Z", fill: YELLOW },
    { d: "M20 32 L36 32 L36 46 L20 46 Z M42 32 L58 32 L58 46 L42 46 Z M64 32 L80 32 L80 46 L64 46 Z" },
    { d: chalkRing(30, 76, 8) },
    { d: chalkRing(70, 76, 8) }
  ],
  kite: [
    { d: "M50 8 L82 44 L50 88 L18 44 Z", fill: PINK },
    { d: "M50 8 L50 88 M18 44 L82 44" },
    { d: "M50 88 C 58 92 42 96 50 100" }
  ],
  balloon: [
    { d: "M50 10 C 28 10 20 34 30 52 C 36 64 46 70 50 70 C 54 70 64 64 70 52 C 80 34 72 10 50 10 Z", fill: RED },
    { d: "M46 70 L54 70 L50 78 Z" },
    { d: "M50 78 C 58 84 42 90 50 96" }
  ],
  book: [
    { d: "M16 28 C 32 22 46 24 50 32 C 54 24 68 22 84 28 L84 74 C 68 68 54 70 50 78 C 46 70 32 68 16 74 Z" },
    { d: "M50 32 L50 78" },
    { d: "M24 40 L42 38 M24 52 L42 50 M58 38 L76 40 M58 50 L76 52" }
  ],
  bag: [
    { d: "M20 40 L80 40 L84 88 L16 88 Z", fill: RED },
    { d: "M36 40 C 36 20 64 20 64 40" },
    { d: "M20 56 L80 56" }
  ],
  umbrella: [
    { d: "M8 54 C 12 22 88 22 92 54 Z", fill: RED },
    { d: "M8 54 C 20 44 26 44 36 54 C 44 44 56 44 64 54 C 74 44 80 44 92 54" },
    { d: "M50 26 L50 82 C 50 92 36 92 36 82" }
  ],
  clock: [
    { d: chalkRing(50, 52, 34) },
    { d: "M50 52 L50 30 M50 52 L66 60" },
    { d: "M50 22 L50 26 M78 52 L74 52 M50 82 L50 78 M22 52 L26 52" }
  ],
  drum: [
    { d: "M22 34 L78 34 L72 72 L28 72 Z", fill: RED },
    { d: chalkRing(50, 34, 28) },
    { d: "M24 44 L44 62 M44 44 L24 62 M56 44 L76 62 M76 44 L56 62" },
    { d: "M14 22 L38 40 M86 22 L62 40" }
  ],
  bottle: [
    { d: "M42 10 L58 10 L58 26 C 68 32 70 40 70 52 L70 84 C 70 90 30 90 30 84 L30 52 C 30 40 32 32 42 26 Z", fill: BLUE },
    { d: "M40 8 L60 8" },
    { d: "M34 54 L66 54" }
  ],
  diya: [
    { d: "M20 62 C 30 82 70 82 80 62 Z", fill: BROWN },
    { d: "M20 62 L80 62" },
    { d: "M50 58 C 42 48 50 36 50 30 C 54 38 60 48 50 58 Z", fill: YELLOW }
  ],
  ice_cream: [
    { d: "M32 46 L68 46 L50 90 Z", fill: BROWN },
    { d: chalkRing(50, 34, 18), fill: PINK },
    { d: "M32 46 L68 46" }
  ],
  circle: [{ d: chalkRing(50, 50, 34) }],
  oval: [{ d: "M50 18 C 22 18 12 82 50 82 C 88 82 78 18 50 18 Z" }],
  square: [{ d: "M18 18 L82 18 L82 82 L18 82 Z" }],
  rectangle: [{ d: "M10 28 L90 28 L90 72 L10 72 Z" }],
  triangle: [{ d: "M50 14 L88 84 L12 84 Z" }],
  diamond: [{ d: "M50 12 L88 50 L50 88 L12 50 Z" }],
  heart: [
    {
      d: "M50 84 C 10 56 16 22 38 22 C 46 22 50 30 50 34 C 50 30 54 22 62 22 C 84 22 90 56 50 84 Z",
      fill: RED
    }
  ],
  line: [{ d: "M10 50 L90 50" }],
  standing_line: [{ d: "M50 10 L50 90" }],
  sleeping_line: [{ d: "M10 50 L90 50" }],
  slanting_line: [{ d: "M18 86 L82 14" }],
  curve: [{ d: "M12 68 C 30 20 70 20 88 68" }],
  zigzag: [{ d: "M10 30 L36 72 L62 30 L88 72" }]
};

/** Tokens that only qualify a noun - "red_ball", "big_apple", "apple_group". */
const MODIFIERS = new Set([
  "outline", "swatch", "group", "big", "small", "tall", "short", "long", "full",
  "empty", "light", "dark", "the", "a", "an", "of", "one", "two", "three",
  "red", "blue", "green", "yellow", "orange", "purple", "pink", "brown",
  "black", "white", "grey", "picture", "image", "icon"
]);

/** Other names the syllabus uses for a drawing that is already here. */
const ALIASES: Record<string, string> = {
  football: "ball",
  cricketball: "ball",
  aam: "mango",
  mangoes: "mango",
  seb: "apple",
  apples: "apple",
  sunny: "sun",
  day: "sun",
  night: "moon",
  rainy: "rain",
  cloudy: "cloud",
  plant: "tree",
  leaves: "leaf",
  lotus: "flower",
  kamal: "flower",
  home: "house",
  hut: "house",
  school: "house",
  kitten: "cat",
  puppy: "dog",
  parrot: "bird",
  // No `crow` here on purpose. The bird drawing is filled with yellow chalk,
  // and a crow is the everyday example of the colour *black* - so it keeps the
  // black-bird emoji rather than being drawn in the wrong colour.
  hen: "bird",
  chick: "bird",
  duck: "bird",
  glass: "cup",
  mug: "cup",
  ship: "boat",
  van: "car",
  taxi: "car",
  jeep: "car",
  round: "circle",
  notebook: "book",
  books: "book",
  schoolbag: "bag",
  raincoat: "umbrella",
  watch: "clock",
  dholak: "drum",
  tabla: "drum",
  lamp: "diya",
  candle: "diya",
  icecream: "ice_cream",
  cone: "ice_cream",
  balloons: "balloon",
  patang: "kite",
  standing: "standing_line",
  sleeping: "sleeping_line",
  slant: "slanting_line",
  left_slant: "slanting_line",
  right_slant: "slanting_line",
  up_curve: "curve",
  down_curve: "curve"
};

function clean(token: string): string {
  return token.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function lookup(key: string): ChalkArt | null {
  if (!key) return null;
  if (ART[key]) return ART[key];
  const alias = ALIASES[key];
  if (alias && ART[alias]) return ART[alias];
  return null;
}

/**
 * The drawing for an asset token, or null when there is none.
 *
 * Null is a real answer and the caller must honour it: a token this file has
 * never seen is shown as its emoji, not as the nearest-looking drawing. A
 * lesson on अनार drawing an apple is the same mistake twice.
 */
export function chalkArtFor(token: string | null | undefined): ChalkArt | null {
  if (!token) return null;
  const key = clean(token);
  const direct = lookup(key);
  if (direct) return direct;

  const parts = key.split("_").filter(Boolean);
  const joined = lookup(parts.join(""));
  if (joined) return joined;

  // The longest run of words first, so "ice_cream_cone" beats "cone".
  for (let size = parts.length; size > 0; size -= 1) {
    for (let start = 0; start + size <= parts.length; start += 1) {
      const run = parts.slice(start, start + size);
      const found = lookup(run.join("_")) ?? lookup(run.join(""));
      if (found) return found;
    }
  }

  // Then the head noun on its own, with the qualifiers dropped.
  for (const part of parts) {
    if (MODIFIERS.has(part)) continue;
    const singular = part.replace(/ies$/, "y").replace(/s$/, "");
    const found = lookup(part) ?? lookup(singular);
    if (found) return found;
  }
  return null;
}

/** The coloured chalk a colour lesson is drawn in. */
export const CHALK_COLOURS: Record<string, string> = {
  red: "#ef6f66",
  blue: "#6fb3e8",
  yellow: "#f3d55b",
  green: "#78cf95",
  orange: "#f0995a",
  purple: "#b490dd",
  pink: "#f094bd",
  brown: "#b98a63",
  black: "#3d4a52",
  white: "#f4f7f4",
  grey: "#b7c2be"
};
