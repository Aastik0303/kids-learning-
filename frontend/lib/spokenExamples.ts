import { VISUAL_FALLBACK, isTextToken, visualIcon } from "@/lib/visualIcon";

/**
 * The examples the teacher says out loud, found in the sentence and timed to it.
 *
 * The explaining turn is three or four sentences and one of them is always a
 * thing the child has seen for themselves - "A is for apple", "round like a
 * ball", "the sun is a circle". A child who cannot read hears that word and
 * gets nothing to look at, because the screen is showing the letter. So: while
 * the example is being *said*, the letter steps aside and the example is on the
 * screen instead, for three seconds, and then the letter comes back.
 *
 * **How the words are found.** Not by a model. The explanation is split into
 * words, each is stripped of punctuation and reduced to its singular, and what
 * is left is looked up in the app's own picture vocabulary - the same
 * `visualIcon` table that draws the answer buttons and the level pages. A word
 * that table has no picture for is not an example, and that is the whole test.
 * It is keyword matching against a closed, hand-written list, which is what
 * this needs to be: the alternative is asking a model which word to illustrate,
 * and a model that picks the picture beside a question is a model deciding what
 * the child sees on the one screen that must not surprise anybody.
 *
 * **When they are shown.** There are no word timings in the audio - Edge TTS
 * returns a clip and nothing else - so each example is placed by where its word
 * falls in the sentence, at the rate that voice actually speaks (`MS_PER_WORD`,
 * about 155 words a minute). It is an estimate and it drifts by a word or two
 * over a long line; the three seconds it stays up is what absorbs the drift.
 *
 * **What is never illustrated**, and this is the part that matters most: any
 * word that is one of the options on screen. On a `match` or `quiz` turn the
 * teacher says the answer's name while leading into the question - "apples are
 * red" in front of a question whose choices are an apple and a ball - and
 * flashing that picture would be handing over the answer. The concept already
 * being drawn is skipped too, for the simpler reason that swapping the letter A
 * for a picture of the letter A is not an example of anything.
 */

export type SpokenExample = {
  /** The word as it will be labelled under the picture. */
  word: string;
  /** The emoji from the app's own vocabulary. Never the neutral fallback. */
  icon: string;
  /** When to put it on the screen, in ms after the narration starts. */
  atMs: number;
};

/** How long one example stays up before the concept comes back. */
export const EXAMPLE_HOLD_MS = 3000;

/**
 * The narration's assumed pace, in ms per word.
 *
 * This is deliberately *not* the 500ms the class's `readingMs` uses. That one
 * is a floor - a slow, four-year-old-facing estimate of how long a line needs
 * to be on screen before the class may move on, where guessing slow is the safe
 * side. This one is a guess at when a particular word actually leaves the
 * speaker, and there the safe side is the other way: place a cue late and the
 * child hears "apple" with the letter still up, then sees an apple for no
 * reason. The backend narrates through Edge TTS at `edge_tts_rate` of "+0%",
 * which is about 155 words a minute.
 */
export const MS_PER_WORD = 390;

/** A beat for the request, the decode and the first syllable. */
const LEAD_MS = 500;

/** At most this many in one explanation. More than three is a slideshow. */
const MAX_EXAMPLES = 3;

/**
 * Words the picture table happens to know but which are almost always doing
 * some other job in a sentence.
 *
 * "We *read* a book", "can you *see* the *line*" - the table has an icon for
 * each of those because a level somewhere asks for one as a picture, but in
 * running narration they are verbs and connective tissue, and illustrating them
 * makes the screen twitch for no reason. The nouns a lesson actually leans on -
 * apple, ball, sun, cat - are all still here.
 */
const NOT_EXAMPLES = new Set([
  "read", "write", "eat", "drink", "run", "jump", "hop", "sing", "dance",
  "sleep", "wash", "smile", "clap", "pause", "group", "question", "shape",
  "colour", "color", "letter", "number", "day", "night", "air", "water",
  "food", "home", "head", "face", "hand", "hands", "line", "stroke", "dot",
  "plus", "minus", "equals", "child", "children", "boy", "girl", "teacher"
]);

/** The singular of a plainly plural word. Nothing clever - the vocabulary is
 *  English nursery nouns, and "apples" and "babies" are the whole problem. */
function singular(word: string): string {
  if (word.length > 4 && word.endsWith("ies")) return `${word.slice(0, -3)}y`;
  if (word.length > 4 && (word.endsWith("ches") || word.endsWith("shes") || word.endsWith("xes"))) {
    return word.slice(0, -2);
  }
  if (word.length > 3 && word.endsWith("s") && !word.endsWith("ss")) return word.slice(0, -1);
  return word;
}

/** A word stripped to its letters, lowercased. Punctuation and quotes go. */
function bare(word: string): string {
  return word.toLowerCase().replace(/[^a-z]/g, "");
}

export function findSpokenExamples(
  speech: string,
  options: {
    /** How many words are said before this text, so the timing lands right. */
    wordsBefore?: number;
    /** The concept already on the screen, and every option offered with it. */
    skip?: (string | undefined)[];
    /** The narration's pace, overridable for a test. */
    msPerWord?: number;
  } = {}
): SpokenExample[] {
  const line = (speech ?? "").trim();
  if (!line) return [];

  const msPerWord = options.msPerWord ?? MS_PER_WORD;
  const wordsBefore = options.wordsBefore ?? 0;

  const forbidden = new Set(
    (options.skip ?? [])
      .filter(Boolean)
      .flatMap((one) => String(one).split(/\s+/))
      .map((one) => singular(bare(one)))
      .filter(Boolean)
  );

  const words = line.split(/\s+/);
  const found: SpokenExample[] = [];
  const seen = new Set<string>();

  words.forEach((raw, index) => {
    if (found.length >= MAX_EXAMPLES) return;

    const word = singular(bare(raw));
    if (word.length < 3) return;
    if (NOT_EXAMPLES.has(word) || forbidden.has(word) || seen.has(word)) return;
    // A single letter or a numeral is the thing being taught, not an example of
    // it - and `visualIcon` would happily hand back a keycap for "3".
    if (isTextToken(word)) return;

    const icon = visualIcon(word);
    if (!icon || icon === VISUAL_FALLBACK) return;

    const atMs = LEAD_MS + (wordsBefore + index) * msPerWord;
    // Two examples inside one hold would fight over the screen, and the first
    // one's exit would take the second one down with it. The later word waits
    // for the next explanation rather than being crammed in.
    if (found.length && atMs - found[found.length - 1].atMs < EXAMPLE_HOLD_MS) return;

    seen.add(word);
    found.push({ word: raw.replace(/[^A-Za-z]/g, ""), icon, atMs });
  });

  return found;
}
