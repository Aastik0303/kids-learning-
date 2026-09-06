"use client";

import { displayToken } from "@/lib/visualIcon";

import { ChalkDrawing } from "./ChalkDrawing";
import { ChalkGlyph } from "./ChalkGlyph";
import { CHALK_COLOURS, chalkArtFor, chalkRing, type ChalkArt } from "./chalkArt";

/**
 * The AI Teacher's blackboard.
 *
 * The class already had a voice and a picture; what it did not have was a
 * board. The picture appeared all at once, finished, at the same moment the
 * teacher began to talk about it - so by the time the words got to the letter,
 * the letter had been sitting there for four seconds and the child had looked
 * away. A blackboard fixes that by being slow on purpose: it is drawn while it
 * is being said, and a child watches a line appear for as long as the line
 * takes.
 *
 * What goes on it is exactly what already came down the wire and nothing else:
 * `visual_kind` / `visual_value`, the thing this card is teaching, chosen on the
 * server. This component adds no content of its own; it only decides how slowly
 * what it was given appears.
 *
 * **The explanation is still not printed.** A paragraph of English on a
 * blackboard is no more readable to a two-year-old than a paragraph of English
 * anywhere else.
 *
 * **And no everyday examples.** The board used to draw two or three of them -
 * the apple beside A, the ball beside a circle - under the thing being taught.
 * The user asked for them to be taken off after they kept turning up beside the
 * wrong concept: a ball under a square, and then under a triangle. The board
 * shows the one thing the card is teaching, and that is all. The strip still
 * exists on Adventure's level notes, where a child is revising rather than
 * being asked something; do not put it back on the class board without being
 * asked to.
 */

export type BlackboardProps = {
  /** Written small in the corner, the way a teacher dates the board. */
  title?: string;
  visualKind?: string;
  visualValue?: string;
  /**
   * Changes when a new turn arrives. The board is wiped and drawn again from
   * nothing, so a repeated question is drawn again rather than sitting there
   * already answered.
   */
  playKey: string;
};

const CHALK_FONT = "'Segoe Print', 'Bradley Hand', 'Comic Sans MS', cursive";

/** When the drawing starts, and how long it takes, after the turn lands. */
const MAIN_DELAY = 250;
const MAIN_MS = 2400;

/** A counting picture: as many rings as there are things, drawn one by one. */
function counters(value: string): ChalkArt {
  const total = Math.max(1, Math.min(Number(value) || 1, 10));
  const perRow = total > 5 ? 5 : total;
  const rows = Math.ceil(total / perRow);
  return Array.from({ length: total }, (_, index) => {
    const row = Math.floor(index / perRow);
    const column = index % perRow;
    const inThisRow = Math.min(perRow, total - row * perRow);
    const gap = 84 / (inThisRow + 1);
    return {
      d: chalkRing(
        8 + gap * (column + 1),
        rows === 1 ? 50 : 34 + row * 32,
        rows === 1 ? 11 : 8
      ),
      fill: CHALK_COLOURS.yellow
    };
  });
}

/** The thing being taught, drawn big in the middle of the board. */
function MainFigure({
  kind,
  value,
  playKey
}: {
  kind: string;
  value: string;
  playKey: string;
}) {
  const size = "h-36 w-36 sm:h-44 sm:w-44";
  const text = value.trim();

  if (kind === "letter" || kind === "number") {
    return (
      <ChalkGlyph
        text={displayToken(text)}
        playKey={playKey}
        delayMs={MAIN_DELAY}
        durationMs={MAIN_MS}
        className={size}
        label={kind === "letter" ? `The letter ${text}` : `The number ${text}`}
      />
    );
  }

  if (kind === "count") {
    return (
      <ChalkDrawing
        strokes={counters(text)}
        playKey={playKey}
        delayMs={MAIN_DELAY}
        durationMs={MAIN_MS}
        className={size}
        label={`${text} things to count`}
      />
    );
  }

  if (kind === "colour") {
    const colour = CHALK_COLOURS[text.toLowerCase()];
    if (!colour) return null;
    return (
      <ChalkDrawing
        strokes={[
          { d: chalkRing(50, 50, 34), fill: colour, fillOpacity: 0.9, stroke: colour, width: 4 }
        ]}
        playKey={playKey}
        delayMs={MAIN_DELAY}
        durationMs={MAIN_MS}
        className={size}
        label={`The colour ${text}`}
      />
    );
  }

  if (kind === "shape") {
    const art = chalkArtFor(text);
    if (art) {
      return (
        <ChalkDrawing
          strokes={art}
          playKey={playKey}
          delayMs={MAIN_DELAY}
          durationMs={MAIN_MS}
          className={size}
          label={`A ${text}`}
        />
      );
    }
    // A shape with no coordinates behind it is written out rather than drawn as
    // some other shape.
    return (
      <ChalkGlyph
        text={text}
        playKey={playKey}
        delayMs={MAIN_DELAY}
        durationMs={MAIN_MS}
        className={size}
        label={`A ${text}`}
      />
    );
  }

  return null;
}

export function Blackboard({ title, visualKind, visualValue, playKey }: BlackboardProps) {
  const hasFigure = Boolean(visualKind && (visualValue ?? "").trim());
  if (!hasFigure && !title) return null;

  return (
    <section className="w-full max-w-2xl" data-testid="blackboard">
      {/* The frame, and the tray of chalk under it. Decoration, and it is the
          reason the drawing reads as a *board* rather than as a dark box. */}
      <div className="rounded-[1.75rem] bg-[linear-gradient(180deg,#b0783f,#8a5730)] p-2.5 shadow-soft">
        <div
          className="relative overflow-hidden rounded-[1.25rem] bg-[#183a30] px-4 py-5 shadow-[inset_0_2px_20px_rgba(0,0,0,0.55)]"
          style={{
            backgroundImage:
              "radial-gradient(120% 80% at 20% 0%, rgba(255,255,255,0.07), rgba(255,255,255,0) 60%), radial-gradient(90% 70% at 85% 100%, rgba(255,255,255,0.05), rgba(255,255,255,0) 55%)"
          }}
        >
          {title ? (
            <p
              className="mb-2 text-left text-sm text-white/55 sm:text-base"
              style={{ fontFamily: CHALK_FONT }}
            >
              {title}
            </p>
          ) : null}

          {/* Wiped and drawn again whenever the turn changes. */}
          <div key={playKey} className="grid justify-items-center gap-3">
            {hasFigure ? (
              <MainFigure
                kind={visualKind as string}
                value={visualValue as string}
                playKey={playKey}
              />
            ) : null}
          </div>
        </div>

        <div className="mt-2 flex items-center justify-end gap-2 px-3" aria-hidden>
          <span className="h-1.5 w-8 rounded-full bg-white/70" />
          <span className="h-1.5 w-5 rounded-full bg-[#f0a0c0]/80" />
          <span className="h-2.5 w-7 rounded-sm bg-[#5d3a1f]" />
        </div>
      </div>
    </section>
  );
}
