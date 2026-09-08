"use client";

import { displayToken } from "@/lib/visualIcon";

import { ChalkDrawing } from "./ChalkDrawing";
import { ChalkGlyph } from "./ChalkGlyph";
import { CHALK_COLOURS, chalkArtFor, chalkRing, type ChalkArt } from "./chalkArt";

/**
 * The thing this card is teaching, drawn.
 *
 * It began as a blackboard - a wooden frame, a green slate, chalk. The board
 * was never the point; the *drawing itself* was, and the point of that is
 * timing. A finished picture that appears the instant the narration starts has
 * been looked at and left before the words reach it, so this one is slow on
 * purpose: it draws itself while it is being said, and a child watches a line
 * appear for as long as the line takes.
 *
 * The frame is gone at the user's request, and with it the whole reason the
 * lines were white. They are ink now, which is why `ChalkDrawing` and
 * `ChalkGlyph` take a `tone`: the drawings are the same coordinates either way,
 * and only what they are drawn *with* changes.
 *
 * In the class this is drawn **on the board the panda is holding** - see
 * `components/avatar/TeacherStage.tsx`, which lays it over the board's face and
 * paints the paws back over the top. That is not the old slate returning: the
 * frame that went was one around the whole card, and this one belongs to the
 * teacher. Nothing here knows about it; the stage sizes whatever it is given.
 *
 * What appears is exactly what came down the wire and nothing else -
 * `visual_kind` / `visual_value`, chosen on the server. This component adds no
 * content of its own; it only decides how slowly what it was given appears.
 *
 * **The explanation is still not printed**, and there are **no everyday
 * examples**: one drawing, of the one thing the card is about. Both of those
 * were asked for, and the second was asked for after a ball kept turning up
 * beside a square.
 */

export type TeachingDrawingProps = {
  visualKind?: string;
  visualValue?: string;
  /**
   * Changes when a new turn arrives, which wipes the drawing and makes it
   * again from nothing - so a question asked a second time is drawn a second
   * time rather than sitting there already finished.
   */
  playKey: string;
};

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

function Figure({ kind, value, playKey }: { kind: string; value: string; playKey: string }) {
  const size = "h-40 w-40 sm:h-52 sm:w-52";
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
          { d: chalkRing(50, 50, 34), fill: colour, fillOpacity: 0.95, stroke: colour, width: 4 }
        ]}
        playKey={playKey}
        delayMs={MAIN_DELAY}
        durationMs={MAIN_MS}
        className={size}
        label={`The colour ${text}`}
      />
    );
  }

  // A shape, or one of the things the syllabus names - a cow, a bus, an apple.
  // Both are looked up the same way, in the one art library, and a token with
  // no coordinates behind it draws nothing rather than something else.
  if (kind === "shape" || kind === "thing") {
    const art = chalkArtFor(text);
    if (art) {
      return (
        <ChalkDrawing
          strokes={art}
          playKey={playKey}
          delayMs={MAIN_DELAY}
          durationMs={MAIN_MS}
          className={size}
          label={kind === "shape" ? `A ${text}` : text.replace(/_/g, " ")}
        />
      );
    }
    if (kind === "shape") {
      // A shape with no coordinates is written out rather than drawn as some
      // other shape. A *thing* is not: the word "cow" written large teaches a
      // child who cannot read nothing at all, so it shows nothing.
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

  return null;
}

export function TeachingDrawing({ visualKind, visualValue, playKey }: TeachingDrawingProps) {
  const value = (visualValue ?? "").trim();
  if (!visualKind || !value) return null;

  return (
    <div key={playKey} className="grid justify-items-center" data-testid="teaching-drawing">
      <Figure kind={visualKind} value={value} playKey={playKey} />
    </div>
  );
}
