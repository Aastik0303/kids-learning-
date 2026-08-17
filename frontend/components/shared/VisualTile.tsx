"use client";

import { displayToken, isTextToken, visualIcon } from "@/lib/visualIcon";

/**
 * One picture from an activity's `visual_items`.
 *
 * Shared so the adventure and Practice render the same authored content the
 * same way — a child who meets "🍎 🍎 🍎" in a lesson must meet the same tile
 * when they practise it, not a different placeholder.
 *
 * A single letter or a numeral shows as itself: seeing "3" teaches more than
 * seeing a picture of three things. Everything else resolves to an emoji.
 */

const shapeClass: Record<string, string> = {
  circle: "rounded-full bg-berry",
  square: "rounded-xl bg-sky",
  triangle: "triangle",
  red: "rounded-full bg-berry",
  blue: "rounded-full bg-sky",
  yellow: "rounded-full bg-sunshine",
  green: "rounded-full bg-leaf"
};

export function VisualTile({
  item,
  domId,
  visualId,
  countLabel,
  highlightClass = ""
}: {
  item: string;
  domId?: string;
  visualId?: string;
  countLabel?: number;
  highlightClass?: string;
}) {
  const shared = {
    id: domId,
    "data-visual-id": visualId,
    "data-visual-item": item,
    "data-count-label": countLabel
  };
  const size = "grid h-20 w-20 place-items-center shadow-soft";

  if (isTextToken(item)) {
    return (
      <span {...shared} className={`${size} rounded-3xl bg-white text-4xl font-black text-ink ${highlightClass}`}>
        {displayToken(item)}
      </span>
    );
  }

  const simple = item.toLowerCase().split(" ").at(-1) ?? "";
  if (shapeClass[simple]) {
    return (
      <span {...shared} aria-label={item} className={`${size} text-5xl ${shapeClass[simple]} ${highlightClass}`}>
        {visualIcon(item)}
      </span>
    );
  }

  return (
    <span {...shared} aria-label={item} className={`${size} rounded-3xl bg-white text-5xl ${highlightClass}`}>
      {visualIcon(item)}
    </span>
  );
}
