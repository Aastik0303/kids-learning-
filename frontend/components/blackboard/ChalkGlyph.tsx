"use client";

import { useEffect, useId, useRef } from "react";

/**
 * A letter, a numeral or a word, written onto the board rather than printed on
 * it.
 *
 * The other drawings are walked along a path, which is only possible because
 * their outlines are hand-written coordinates. A glyph has no path to walk:
 * "A" is whatever shape the font makes of it, and क is a shape no rule here
 * knows. So the writing is done as a wipe - the glyph is revealed left to
 * right with a chalk tip at the edge - which is close enough to a hand for a
 * child to watch, works for every script the syllabus uses, and cannot get a
 * letter's stroke order wrong by guessing at it.
 *
 * The letter is the lesson, so it is drawn in whatever font can render it: a
 * Devanagari letter must never fall back to an empty box.
 */

export type ChalkGlyphProps = {
  text: string;
  /** Changing this wipes the board and writes it again. */
  playKey: string;
  durationMs?: number;
  delayMs?: number;
  /** The chalk to write in. Colour lessons write in their own colour. */
  colour?: string;
  className?: string;
  label?: string;
};

const CHALK = "#f6f8f3";
const INK = "#25313f";
const GLYPH_FONT = "'Segoe Print', 'Bradley Hand', system-ui, 'Nirmala UI', sans-serif";

function sizeFor(text: string): number {
  // Counted in code points, not UTF-16 units: अं is one letter written with two
  // of them, and sizing it as two would shrink a single Hindi letter by a fifth.
  //
  // A letter is written as large as the box will take. The sizes below used to
  // leave a third of the box empty round a single character, which was only
  // visible once the drawings beside it started filling theirs: on the board
  // the teacher holds, the letter of a letters lesson came out smaller than the
  // circle of a shapes one. A capital at 88 is about 62 units of ink inside a
  // 100-unit box, which is the most that fits with the widest letters - W, M,
  // and the Devanagari that carries a matra above and below - still inside it.
  const length = Array.from(text.trim()).length;
  if (length <= 1) return 88;
  if (length === 2) return 66;
  if (length === 3) return 50;
  return Math.max(18, Math.round(155 / length));
}

export function ChalkGlyph({
  text,
  playKey,
  durationMs = 1500,
  delayMs = 0,
  colour = INK,
  className,
  label
}: ChalkGlyphProps) {
  // React's own id, with the colons taken out - an id with a colon in it is
  // valid HTML and a nuisance everywhere else, `url(#...)` included.
  const clipId = `chalk-${useId().replace(/[^a-zA-Z0-9-]/g, "")}`;
  const paneRef = useRef<SVGRectElement | null>(null);
  const tip = useRef<SVGCircleElement | null>(null);

  useEffect(() => {
    const pane = paneRef.current;
    if (!pane) return;

    const finish = () => {
      pane.setAttribute("width", "100");
      if (tip.current) tip.current.style.opacity = "0";
    };

    const still =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (still) {
      finish();
      return;
    }

    pane.setAttribute("width", "0");
    if (tip.current) tip.current.style.opacity = "0";

    let frame = 0;
    const startedAt = performance.now() + delayMs;
    const step = (now: number) => {
      const elapsed = now - startedAt;
      if (elapsed < 0) {
        frame = requestAnimationFrame(step);
        return;
      }
      const progress = Math.min(1, elapsed / durationMs);
      const edge = progress * 100;
      pane.setAttribute("width", `${edge}`);
      if (tip.current) {
        tip.current.setAttribute("cx", `${edge}`);
        // A little up and down, because a hand writing a letter does not travel
        // in a straight line across the board.
        tip.current.setAttribute("cy", `${56 - Math.sin(progress * Math.PI * 3) * 14}`);
        tip.current.style.opacity = progress < 1 ? "1" : "0";
      }
      if (progress < 1) frame = requestAnimationFrame(step);
      else finish();
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [playKey, durationMs, delayMs, text]);

  const size = sizeFor(text);

  return (
    <svg
      viewBox="0 0 100 100"
      role="img"
      aria-label={label ?? text}
      className={className}
      data-chalk-glyph={text}
    >
      <defs>
        <clipPath id={clipId}>
          <rect ref={paneRef} x="0" y="0" width="0" height="100" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`}>
        <text
          x="50"
          y="52"
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size}
          fontWeight={700}
          fontFamily={GLYPH_FONT}
          fill={colour}
          fillOpacity={0.25}
        >
          {text}
        </text>
        <text
          x="50"
          y="52"
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size}
          fontWeight={700}
          fontFamily={GLYPH_FONT}
          fill="none"
          stroke={colour}
          strokeWidth={1.6}
          strokeLinejoin="round"
        >
          {text}
        </text>
      </g>
      <circle ref={tip} cx={0} cy={56} r={2.4} fill={colour} style={{ opacity: 0 }} />
    </svg>
  );
}
