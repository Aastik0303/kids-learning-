import { View } from "react-native";

import { ChalkDrawing } from "@/components/blackboard/ChalkDrawing";
import { ChalkGlyph } from "@/components/blackboard/ChalkGlyph";
import {
  CHALK_COLOURS,
  chalkArtFor,
  chalkRing,
  type ChalkArt,
} from "@/components/blackboard/chalkArt";
import { displayToken } from "@/lib/visualIcon";

/**
 * The thing this card is teaching, drawn.
 *
 * What appears is exactly what came down the wire and nothing else -
 * `visual_kind` / `visual_value`, chosen on the server. This component adds no
 * content of its own; it only decides how slowly what it was given appears.
 *
 * The explanation is **not** printed here and there are no everyday examples:
 * one drawing, of the one thing the card is about. Both of those were asked for
 * on the web, and this client is the same class, so it keeps the same rule.
 *
 * A token with no coordinates behind it draws **nothing** rather than a
 * near-miss - the rule `visualIcon` keeps for अनार, which was showing a child
 * सेब because an apple emoji was the closest thing Unicode had.
 */

export type TeachingDrawingProps = {
  visualKind?: string;
  visualValue?: string;
  /**
   * Changes when a new turn arrives, which wipes the drawing and makes it again
   * from nothing - so a question asked a second time is drawn a second time
   * rather than sitting there already finished.
   */
  playKey: string;
};

/** When the drawing starts, and how long it takes, after the turn lands. */
const MAIN_DELAY = 250;
const MAIN_MS = 2400;

/**
 * A counting picture: as many rings as there are things, drawn one by one.
 *
 * Each ring gets a column of its own and is drawn inside it. Spacing them by
 * the gaps between them and then giving them a fixed radius is what made four
 * of them overlap into a chain, and a child counting a chain does not count
 * four.
 */
function counters(value: string): ChalkArt {
  const total = Math.max(1, Math.min(Number(value) || 1, 10));
  const perRow = total > 5 ? 5 : total;
  const rows = Math.ceil(total / perRow);
  return Array.from({ length: total }, (_, index) => {
    const row = Math.floor(index / perRow);
    const column = index % perRow;
    const inThisRow = Math.min(perRow, total - row * perRow);
    const cell = 84 / inThisRow;
    // Four tenths of the column, so there is always a clear tenth of a column
    // of board between one ring and the next, whatever the count.
    const radius = Math.min(cell * 0.4, rows === 1 ? 14 : 11);
    return {
      d: chalkRing(8 + cell * (column + 0.5), rows === 1 ? 50 : 34 + row * 32, radius),
      fill: CHALK_COLOURS.yellow,
    };
  });
}

function Figure({ kind, value, playKey }: { kind: string; value: string; playKey: string }) {
  const text = value.trim();

  if (kind === "letter" || kind === "number") {
    return (
      <ChalkGlyph
        text={displayToken(text)}
        playKey={playKey}
        delayMs={MAIN_DELAY}
        durationMs={MAIN_MS}
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
          { d: chalkRing(50, 50, 34), fill: colour, fillOpacity: 0.95, stroke: colour, width: 4 },
        ]}
        playKey={playKey}
        delayMs={MAIN_DELAY}
        durationMs={MAIN_MS}
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
    <View style={{ flex: 1, width: "100%" }} testID="teaching-drawing">
      <Figure kind={visualKind} value={value} playKey={playKey} />
    </View>
  );
}
