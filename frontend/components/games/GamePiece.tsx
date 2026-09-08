"use client";

import { exampleWord } from "@/components/curriculum/ExampleStrip";
import { VISUAL_FALLBACK, displayToken, isTextToken, visualIcon } from "@/lib/visualIcon";

/**
 * One thing on a game board: a picture, big, with its word under it.
 *
 * The rule the whole app keeps about pictures is kept here too — **a token with
 * no artwork behind it draws nothing rather than a near-miss**. `visualIcon`
 * gives back a neutral blue diamond for a token it does not know, and a memory
 * game dealt four neutral diamonds is a game a child cannot win and cannot be
 * told why. So `pictureFor` returns "" for those, and the games ask
 * `hasPicture` before they put a token on the board at all.
 *
 * A letter, a numeral or a Devanagari letter is drawn as **itself**, written
 * large. That is the thing being taught on those levels, not a label for it.
 */

/** The picture for an asset token, or "" when the app has none for it. */
export function pictureFor(token: string): string {
  const words = String(token ?? "").replace(/_/g, " ").trim();
  if (!words) return "";
  if (isTextToken(words)) return displayToken(words);
  const resolved = visualIcon(words);
  return resolved && resolved !== VISUAL_FALLBACK ? resolved : "";
}

/** Whether this token can be shown at all. A game never deals one that cannot. */
export function hasPicture(token: string): boolean {
  return pictureFor(token) !== "";
}

/** Whether the picture *is* text — a letter or a numeral drawn as itself. */
export function isGlyph(token: string): boolean {
  const words = String(token ?? "").replace(/_/g, " ").trim();
  return isTextToken(words) || /^[A-Za-z0-9ऀ-ॿ]{1,3}$/.test(pictureFor(token));
}

/** The word said under a picture. Never under a letter: writing "a" under A
 *  says the same thing twice, and under अनार it would transliterate the very
 *  word the level is teaching. */
export function wordFor(token: string): string {
  return isGlyph(token) ? "" : exampleWord(token);
}

export type GamePieceProps = {
  token: string;
  /** How big the picture is drawn. The word under it stays readable at all three. */
  size?: "sm" | "md" | "lg";
  /** Hide the word, for a board where the picture has to carry it alone. */
  quiet?: boolean;
};

const PICTURE_SIZE = { sm: "text-4xl", md: "text-5xl", lg: "text-6xl" } as const;
const GLYPH_SIZE = { sm: "text-3xl", md: "text-4xl", lg: "text-5xl" } as const;

export function GamePiece({ token, size = "md", quiet = false }: GamePieceProps) {
  const picture = pictureFor(token);
  const glyph = isGlyph(token);
  const word = quiet ? "" : wordFor(token);

  return (
    <span className="grid justify-items-center gap-1">
      <span
        aria-hidden
        className={`${glyph ? `${GLYPH_SIZE[size]} font-black text-ink` : PICTURE_SIZE[size]} leading-none`}
      >
        {picture}
      </span>
      {word ? (
        <span className="text-sm font-black capitalize text-ink/70 sm:text-base">{word}</span>
      ) : (
        <span className="sr-only">{exampleWord(token)}</span>
      )}
    </span>
  );
}
