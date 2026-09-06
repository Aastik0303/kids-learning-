"use client";

import { VISUAL_FALLBACK, visualIcon } from "@/lib/visualIcon";

/**
 * The everyday things a lesson names, drawn where its explanation used to be.
 *
 * The AI Teacher writes three or four sentences for every teaching turn and
 * says them out loud. It used to *print* them too, which put a paragraph of
 * English in front of a two-year-old who cannot read a word of it, in the one
 * piece of screen they could actually have used. The words are still written,
 * still spoken and still what the class is teaching — they are just for the ear
 * now, and this is what the eye gets instead: the apple beside the letter A,
 * the ball beside the circle.
 *
 * The server names the things (`example_items`, out of the author's own
 * activities) and this draws them. A token with no artwork behind it is
 * dropped rather than shown as a neutral mark, and a strip with nothing left in
 * it renders nothing at all.
 */

/** A word a child reads under the picture, out of the asset token. */
const WORDS: Record<string, string> = {
  orangefruit: "orange",
  icecream: "ice cream",
  fireengine: "fire engine",
  peapod: "pea pod",
  schoolbag: "school bag",
  postoffice: "post office",
  swimmingpool: "swimming pool",
  trafficlight: "traffic light",
  toothbrush: "toothbrush"
};

/**
 * Exported because the blackboard draws the same examples in chalk and has to
 * caption them with the same word - two spellings of "ice cream" on one screen
 * is two words to a child who is learning both.
 */
export function exampleWord(token: string): string {
  const key = token.trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
  return WORDS[key] ?? token.trim().replace(/_/g, " ");
}

const wordFor = exampleWord;

/**
 * Whether the resolver gave back text rather than a picture — a Devanagari
 * word such as अनार, or a letter. Those are shown as themselves with no caption:
 * writing "anar" under अनार transliterates the very word the level is teaching,
 * which is exactly what the curriculum does not do.
 */
function isWordIcon(icon: string): boolean {
  return /[A-Za-z0-9ऀ-ॿ]/.test(icon);
}

export type ExampleStripProps = {
  items: string[];
};

export function ExampleStrip({ items }: ExampleStripProps) {
  const shown = (items ?? [])
    .map((token) => ({ token, icon: visualIcon(token) }))
    .filter((one) => one.icon && one.icon !== VISUAL_FALLBACK)
    .slice(0, 3);

  if (!shown.length) return null;

  return (
    <ul
      className="flex flex-wrap items-stretch justify-center gap-3"
      data-testid="example-strip"
    >
      {shown.map(({ token, icon }) => {
        const word = isWordIcon(icon) ? "" : wordFor(token);
        return (
          <li
            key={token}
            className="grid min-w-28 justify-items-center gap-1 rounded-3xl bg-white px-5 py-4 shadow-soft"
          >
            <span
              aria-hidden
              className={isWordIcon(icon) ? "text-4xl font-black text-ink" : "text-5xl leading-none"}
            >
              {icon}
            </span>
            {word ? (
              <span className="text-base font-black capitalize text-ink/70">{word}</span>
            ) : (
              <span className="sr-only">{token}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
