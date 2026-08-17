/**
 * Turns an asset token from authored content into something a child can see.
 *
 * Activities name their pictures as tokens — "apple", "red_ball", "circle_outline",
 * "basket_2". These are asset identifiers, the same way an image filename would
 * be, not curriculum names: no class, subject or topic string appears here.
 * Until real illustrations exist, an emoji stands in for each one.
 *
 * The resolver is deliberately forgiving. Content is authored by hand and will
 * keep inventing tokens, so an unknown one degrades to its head noun, then to a
 * neutral mark — it never renders a blank.
 */

const NOUNS: Record<string, string> = {
  // shapes
  circle: "⭕", square: "🟦", triangle: "🔺", rectangle: "▭", oval: "⬭",
  star: "⭐", diamond: "🔶", semicircle: "◗", shape: "🔷",
  // colours
  red: "🔴", blue: "🔵", green: "🟢", yellow: "🟡", orange: "🟠",
  purple: "🟣", pink: "🌸", brown: "🟤", black: "⚫", white: "⚪", grey: "🩶",
  // food
  apple: "🍎", banana: "🍌", mango: "🥭", orangefruit: "🍊", grapes: "🍇",
  tomato: "🍅", potato: "🥔", carrot: "🥕", candy: "🍬", cake: "🎂",
  bun: "🍞", bread: "🍞", milk: "🥛", egg: "🥚", icecream: "🍨", peapod: "🫛",
  cherry: "🍒", food: "🍽️", water: "💧", juice: "🧃",
  watermelon: "🍉", peas: "🫛", onion: "🧅", spinach: "🥬",
  // animals
  cat: "🐱", dog: "🐶", cow: "🐄", lion: "🦁", tiger: "🐯", elephant: "🐘",
  monkey: "🐵", rabbit: "🐰", goat: "🐐", horse: "🐴", camel: "🐫",
  fish: "🐟", bird: "🐦", parrot: "🦜", crow: "🐦‍⬛", duck: "🦆", hen: "🐔",
  chick: "🐤", calf: "🐄", cub: "🦁", puppy: "🐶", kitten: "🐱", yak: "🐃",
  zebra: "🦓", snake: "🐍", frog: "🐸", butterfly: "🦋", spider: "🕷️",
  sheep: "🐑", pig: "🐷", bear: "🐻", turtle: "🐢", whale: "🐳", giraffe: "🦒",
  // nature
  sun: "☀️", moon: "🌙", cloud: "☁️", rain: "🌧️", tree: "🌳", flower: "🌼",
  leaf: "🍃", plant: "🌱", seed: "🌰", root: "🥕", grass: "🌿", sky: "🌌",
  stone: "🪨", rock: "🪨", sand: "🏖️", air: "💨", nest: "🪹", feather: "🪶",
  rainbow: "🌈", night: "🌙", day: "☀️",
  // weather as a child names it, not as a noun: "sunny" is what a Play Group
  // activity asks for, and it must not fall through to the neutral mark.
  sunny: "☀️", rainy: "🌧️", cloudy: "☁️", windy: "💨",
  // transport
  car: "🚗", bus: "🚌", train: "🚂", cycle: "🚲", bike: "🚲", boat: "⛵",
  ship: "🚢", aeroplane: "✈️", plane: "✈️", rocket: "🚀", truck: "🚚",
  ambulance: "🚑", fireengine: "🚒", auto: "🛺", scooter: "🛵",
  bicycle: "🚲", airplane: "✈️",
  // people
  doctor: "👩‍⚕️", teacher: "👩‍🏫", policeman: "👮", postman: "📮", farmer: "👨‍🌾",
  carpenter: "🔨", child: "🧒", boy: "👦", girl: "👧", baby: "👶",
  mother: "👩", father: "👨", grandmother: "👵", grandfather: "👴",
  sister: "👧", brother: "👦", family: "👨‍👩‍👧", queen: "👸", clown: "🤡",
  // body
  eyes: "👀", ears: "👂", nose: "👃", mouth: "👄", hands: "✋", hand: "✋",
  legs: "🦵", feet: "🦶", hair: "💇", head: "🙂", face: "🙂", tongue: "👅",
  thumb: "👍", fingers: "🖐️", toes: "🦶",
  // objects
  ball: "⚽", balloon: "🎈", book: "📕", bag: "🎒", bottle: "🍼", box: "📦",
  basket: "🧺", cup: "🥤", glass: "🥛", plate: "🍽️", bed: "🛏️", chair: "🪑",
  table: "🪑", door: "🚪", house: "🏠", home: "🏠", school: "🏫", clock: "🕒",
  kite: "🪁", jug: "🫗", hat: "🎩", cap: "🧢", umbrella: "☂️", van: "🚐",
  watch: "⌚", xylophone: "🎼", toy: "🧸", doll: "🪆", block: "🧱", brick: "🧱",
  clay: "🧱", paper: "📄", glue: "🧴", pencil: "✏️", crayon: "🖍️", gift: "🎁",
  coin: "🪙", money: "💰", key: "🗝️", drum: "🥁", swing: "🛝", slide: "🛝",
  stove: "🔥", fridge: "🧊", dustbin: "🗑️", brush: "🪥", soap: "🧼",
  sweater: "🧥", shoe: "👟", calendar: "📅", diya: "🪔", lamp: "🪔",
  bone: "🦴", pot: "🏺", gamla: "🪴", floor: "⬜", footpath: "🛣️", road: "🛣️",
  knife: "🔪", spoon: "🥄", helmet: "⛑️",
  building: "🏢", swimmingpool: "🏊", playground: "🛝", park: "🏞️",
  // signals and marks
  trafficlight: "🚦", signal: "🚦", dot: "⚫", tenframe: "🔟", group: "🔢",
  plus: "➕", minus: "➖", equals: "🟰", question: "❓",
  line: "➖", curve: "〰️", zigzag: "⚡", stroke: "✏️", slant: "📐", slanting: "📐",
  // feelings — a face is the only way a pre-reader can be asked about one
  happy: "😊", sad: "😢", angry: "😠", scared: "😨", excited: "🤩", sleepy: "😴",
  // actions and the rest of the authored vocabulary
  clap: "👏", pause: "⏸️", skin: "🖐️", children: "🧒", uncle: "👨", aunt: "👩",
  schoolbag: "🎒", matches: "🔥", plough: "🚜", stethoscope: "🩺",
  helicopter: "🚁", jump: "🤸", run: "🏃", hop: "🦘", dance: "💃", sing: "🎤",
  sleep: "😴", eat: "🍽️", drink: "🥤", wash: "🧼", read: "📖", write: "✍️",
  smile: "😊", pollution: "🏭", smoke: "💨", noise: "🔊", police: "👮",
  postoffice: "🏤", station: "🚉", market: "🏪", hospital: "🏥",
  // Hindi picture words, alongside the ones already here (aam, imli, gamla,
  // kamal, diya). The token is an asset name, so a Hindi lesson can ask for the
  // picture it actually names.
  anar: "🍎", eekh: "🎋", ullu: "🦉", oon: "🧶", ainak: "👓", namaste: "🙏",
  bat: "🏏", horn: "📯", kennel: "🏠", leaves: "🍃", lotus: "🪷", kamal: "🪷",
  mat: "🧶", pomegranate: "🫐", queue: "🚶", raincoat: "🧥", rat: "🐀",
  river: "🏞️", street: "🛣️", taxi: "🚕", toothbrush: "🪥", zip: "🤐",
  imli: "🌰", aam: "🥭", mangoes: "🥭", colours: "🌈", twelve: "🕛",
};

/** Words that only qualify a noun, e.g. "red_ball" or "circle_outline". */
const MODIFIERS = new Set([
  "outline", "swatch", "group", "big", "small", "tall", "short", "long",
  "full", "empty", "near", "far", "front", "behind", "above", "below",
  "top", "bottom", "inside", "outside", "light", "dark", "heavy", "thick",
  "thin", "wide", "narrow", "in", "out", "on", "under", "beside", "next",
  "left", "right", "middle", "mixed", "same", "different", "letter",
  "number", "shape", "colour", "color", "the", "is", "a", "an", "of",
]);

const DIGITS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"];

const FALLBACK = "🔹";

function clean(token: string): string {
  return token.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

/**
 * A token that should be shown as its own text rather than an icon: a single
 * letter, a number, or a comparison sign. Showing "3" as a numeral teaches more
 * than showing three of something.
 */
export function isTextToken(token: string): boolean {
  const raw = token.trim();
  if (/^[A-Za-z]$/.test(raw)) return true;
  if (/^\d{1,3}$/.test(raw)) return true;
  if (/^[<>=+\-?]$/.test(raw)) return true;
  // A Devanagari letter is shown as itself, the same way "A" and "3" are.
  // `clean` below strips everything outside a-z0-9, so without this a swar
  // would fall through to the neutral mark and Hindi would render as blanks.
  // Up to three code points, because अं and अः are a letter plus its mark.
  if (/^[ऀ-ॿ]{1,3}$/.test(raw)) return true;
  return false;
}

/**
 * How a text token is written for a child.
 *
 * A single letter is always shown as a capital. Capitals are what the curriculum
 * teaches first, and they are what `visualIcon` already produces for a
 * `letter_c` picture — so a lowercase answer button beside an uppercase picture
 * of the same letter reads as two different letters to a child still learning
 * them. The token itself is untouched; only its display changes.
 */
export function displayToken(token: string): string {
  const raw = token.trim();
  return /^[A-Za-z]$/.test(raw) ? raw.toUpperCase() : raw;
}

export function visualIcon(token: string | null | undefined): string {
  if (!token) return FALLBACK;
  const raw = token.trim();

  // A bare digit gets a keycap; multi-digit numbers are shown as text elsewhere.
  if (/^\d$/.test(raw)) return DIGITS[Number(raw)];

  const key = clean(raw);
  if (!key) return FALLBACK;
  if (NOUNS[key]) return NOUNS[key];

  const parts = key.split("_").filter(Boolean);

  // "letter_A" / "letter_A_outline" -> show the letter itself. Likewise
  // "number_15_outline" -> the numeral. A tracing outline should show the very
  // glyph the child is about to draw, not a picture of something else.
  //
  // "letter_small_a" is the one token that keeps its lowercase. Nursery teaches
  // Aa as a single letter — big and small on the same card — so the small form
  // has to be shown as a small letter or the card teaches nothing.
  if (parts[0] === "letter" && parts[1] === "small" && parts[2]?.length === 1) {
    return parts[2].toLowerCase();
  }
  if (parts[0] === "letter" && parts[1]?.length === 1) return parts[1].toUpperCase();
  if (parts[0] === "number" && /^\d+$/.test(parts[1] ?? "")) return parts[1];
  if (parts[0] === "hindi" && parts[1]) return parts[1];

  // Longest match first, so "traffic_light" beats "light".
  const joined = parts.join("");
  if (NOUNS[joined]) return NOUNS[joined];

  for (let size = parts.length; size > 0; size -= 1) {
    for (let start = 0; start + size <= parts.length; start += 1) {
      const candidate = parts.slice(start, start + size).join("");
      if (NOUNS[candidate]) return NOUNS[candidate];
    }
  }

  // Drop qualifiers and try the head noun on its own.
  for (const part of parts) {
    if (MODIFIERS.has(part)) continue;
    const singular = part.replace(/(ies)$/, "y").replace(/s$/, "");
    if (NOUNS[part]) return NOUNS[part];
    if (NOUNS[singular]) return NOUNS[singular];
  }

  return FALLBACK;
}
