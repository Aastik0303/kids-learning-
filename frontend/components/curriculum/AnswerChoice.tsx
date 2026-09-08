"use client";

import { VISUAL_FALLBACK, displayToken, isTextToken, visualIcon } from "@/lib/visualIcon";

/**
 * What one answer button shows.
 *
 * The word on its own is not an answer a two-year-old can give. "monkey" and
 * "bear" are the same picture to a child who cannot read - two grey shapes of
 * about the same length - so the whole question comes down to guessing, and a
 * level about animals ends up measuring reading.
 *
 * So every choice gets a picture. Three places it can come from, in order:
 *
 * 1. **The author's own emoji**, which arrives inside the label - the syllabus
 *    writes `option_emojis` for many activities and the server appends them, so
 *    a shapes button comes down as "circle ⭕". It is pulled out of the words
 *    and drawn big rather than left sitting after them at reading size.
 * 2. **The app's picture vocabulary** (`visualIcon`), for the activities whose
 *    author wrote no emoji at all - which is how "Tap the monkey!" arrived with
 *    two bare words under it.
 * 3. **The word itself, written big**, when it is a letter or a numeral. Those
 *    are the thing being taught, not a label for it.
 *
 * A choice nothing can illustrate keeps the plain word, which is what a grown-up
 * reads over the child's shoulder anyway - and so does **every** choice when two
 * of them would come out as the same picture. "Standing line" and "sleeping
 * line" both resolve to a dash; two identical buttons are worse than two words,
 * because a word can at least be read out to the child.
 *
 * **The label is never changed, only how it is drawn.** The page sends the
 * option string back exactly as it was given, and the server marks a tap by
 * which button it was - so nothing here can move the answer.
 */

/**
 * Code points that are a picture in their own right.
 *
 * The small geometric squares - ▫️ ◽ ▪️ - are deliberately **not** in here. The
 * syllabus uses them as a placeholder where it had no picture in mind, so
 * treating one as the button's picture would draw a blank square for "mat" and
 * another for "rat" and hide the two the app actually has.
 */
function isPicture(code: number): boolean {
  return (
    (code >= 0x1f000 && code <= 0x1faff) || // faces, animals, objects, symbols
    (code >= 0x2600 && code <= 0x27bf) || // misc symbols and dingbats
    (code >= 0x2b00 && code <= 0x2bff) ||
    (code >= 0x231a && code <= 0x231b) ||
    (code >= 0x23e9 && code <= 0x23fa) ||
    (code >= 0x2194 && code <= 0x21aa) ||
    (code >= 0x1f1e6 && code <= 0x1f1ff) || // flags
    code === 0x24c2 ||
    code === 0x203c ||
    code === 0x2049 ||
    code === 0x2122 ||
    code === 0x2139 ||
    code === 0x3030 ||
    code === 0x303d ||
    code === 0x3297 ||
    code === 0x3299
  );
}

/**
 * A mark that belongs to the picture before it and is nothing on its own: the
 * variation selectors, the zero-width joiner of "👩‍⚕️", a skin tone, and the
 * enclosing keycap of "1️⃣".
 */
function isMark(code: number): boolean {
  return (
    code === 0xfe0f ||
    code === 0xfe0e ||
    code === 0x200d ||
    code === 0x20e3 ||
    (code >= 0x1f3fb && code <= 0x1f3ff)
  );
}

/**
 * The picture the author put in the label, and the words without it.
 *
 * Two shapes need care. A **keycap** - "1️⃣" - is an ordinary digit followed by
 * the enclosing mark, so the digit has to be moved into the picture or the
 * button reads "1 1" and every number on the screen comes out looking the
 * same. And a mark on its own is **not** a picture: "▫️" without its square is
 * an invisible character, and treating that as the button's picture draws an
 * empty box where the word should have been.
 */
export function splitChoice(option: string): { emoji: string; words: string } {
  const characters = Array.from(option ?? "");
  const picture: string[] = [];
  const rest: string[] = [];
  let drawn = false;

  for (let index = 0; index < characters.length; index += 1) {
    const character = characters[index];
    const code = character.codePointAt(0) ?? 0;
    const next = characters[index + 1]?.codePointAt(0) ?? 0;
    const after = characters[index + 2]?.codePointAt(0) ?? 0;

    if (
      /^[0-9#*]$/.test(character) &&
      (next === 0x20e3 || (next === 0xfe0f && after === 0x20e3))
    ) {
      picture.push(character);
      drawn = true;
      continue;
    }
    if (isPicture(code)) {
      picture.push(character);
      drawn = true;
      continue;
    }
    if (isMark(code)) {
      if (picture.length) picture.push(character);
      continue;
    }
    rest.push(character);
  }

  return {
    emoji: drawn ? picture.join("").trim() : "",
    words: rest.join("").replace(/\s+/g, " ").trim()
  };
}

/** The picture for one choice, or "" when it has none. */
function pictureFor(option: string): string {
  const { emoji, words } = splitChoice(option);
  if (emoji) return emoji;
  // A letter or a numeral is the thing being taught, not a label for it, so it
  // is written big as its own picture.
  if (words && isTextToken(words)) return displayToken(words);
  const resolved = words ? visualIcon(words) : "";
  return resolved && resolved !== VISUAL_FALLBACK ? resolved : "";
}

export type AnswerChoiceProps = {
  /** The option exactly as the server sent it. */
  option: string;
  /** Every choice on the screen, so two of them cannot end up identical. */
  offered?: string[];
};

export function AnswerChoice({ option, offered }: AnswerChoiceProps) {
  const { words } = splitChoice(option);
  const isGlyph = Boolean(words) && isTextToken(words);
  const own = pictureFor(option);
  const clash = (offered ?? []).some(
    (other) => other !== option && own !== "" && pictureFor(other) === own
  );
  const picture = clash ? "" : own;

  if (!picture) {
    return <span className="text-xl font-black text-ink">{displayToken(words || option)}</span>;
  }

  // The picture carries the button and the word sits under it, small - the way
  // round a child who cannot read needs them.
  //
  // `answer-picture` and `answer-word` are hooks for the surface around it, not
  // styling of their own: the class grows both on a phone, where the answers
  // are one of the two things the screen is for. Nothing here decides a size.
  return (
    <span className="grid justify-items-center gap-1">
      <span
        aria-hidden
        className={`answer-picture ${isGlyph ? "text-4xl font-black leading-none" : "text-5xl leading-none"}`}
      >
        {picture}
      </span>
      {words && !isGlyph ? (
        <span className="answer-word text-base font-black capitalize text-ink/70">{words}</span>
      ) : (
        <span className="sr-only">{words || option}</span>
      )}
    </span>
  );
}
