"use client";

import { displayToken, isTextToken } from "@/lib/visualIcon";

const colourOptions: Record<string, string> = {
  red: "bg-red-500",
  blue: "bg-blue-500",
  yellow: "bg-yellow-400",
  green: "bg-green-500",
  orange: "bg-orange-500",
  purple: "bg-purple-500",
  pink: "bg-pink-400",
  black: "bg-black",
  white: "border border-ink/20 bg-white",
  brown: "bg-amber-800"
};

const shapeOptions: Record<string, string> = {
  circle: "●",
  square: "■",
  triangle: "▲",
  rectangle: "▭",
  star: "★",
  diamond: "◆",
  oval: "⬭",
  heart: "♥"
};

export function VoiceFallbackOptions({
  options,
  disabled,
  onAnswer
}: {
  options: string[];
  disabled?: boolean;
  onAnswer: (answer: string) => void;
}) {
  return (
    <div data-guide-id="answer-options" className="grid gap-3 sm:grid-cols-3">
      {options.map((option) => {
        const normalized = option.toLowerCase();
        const colourClass = colourOptions[normalized];
        const shape = shapeOptions[normalized];
        // A letter or a numeral is the whole answer, so it gets the room a
        // picture would. Anything else is a word and stays at reading size.
        const isGlyph = isTextToken(option);
        return (
        <button
          key={option}
          disabled={disabled}
          onClick={() => onAnswer(option)}
          className={`pressable min-h-16 rounded-3xl border-2 border-transparent bg-white px-4 py-3 font-black text-ink shadow-soft transition hover:border-ink/10 disabled:opacity-50 ${
            isGlyph ? "text-5xl leading-none" : "text-lg"
          }`}
          type="button"
        >
          {colourClass ? <span className={`mr-3 inline-block h-8 w-8 rounded-full align-middle ring-2 ring-ink/10 ${colourClass}`} aria-hidden="true" /> : null}
          {shape ? <span className="mr-3 inline-block min-w-8 align-middle text-3xl leading-none text-sky" aria-hidden="true">{shape}</span> : null}
          {displayToken(option)}
        </button>
        );
      })}
    </div>
  );
}
