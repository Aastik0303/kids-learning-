"use client";

import { useEffect, useMemo, useRef } from "react";

import type { ChalkArt } from "./chalkArt";

/**
 * A drawing that draws itself, the way a teacher's hand does.
 *
 * Every line is revealed along its own length - `stroke-dasharray` set to the
 * path's length and the offset walked down to zero - and the lines are walked
 * in the order the artwork lists them, so the child sees the outline of the
 * apple made before the stalk is put on it. A small chalk tip rides the end of
 * whichever line is being drawn, because what makes a hand look like a hand is
 * that there is something *at* the moving end.
 *
 * The animation is driven by one `requestAnimationFrame` loop writing straight
 * to the DOM rather than by React state. A five-stroke drawing at 60fps is 300
 * renders a second of a page that also has a microphone, a narration promise
 * and an auto-advance clock on it; none of those need to know where the chalk
 * has got to.
 *
 * A child who has asked their system not to animate things gets the finished
 * drawing immediately. So does anything without a layout engine behind it - a
 * test renderer has no `getTotalLength`, and a picture that never appears
 * because the geometry could not be measured is worse than one that does not
 * move.
 */

export type ChalkDrawingProps = {
  strokes: ChalkArt;
  /** Changing this wipes the board and draws again from nothing. */
  playKey: string;
  /** How long the whole drawing takes, once it starts. */
  durationMs?: number;
  /** How long the board stays blank first, so drawings can follow each other. */
  delayMs?: number;
  /** What the drawing is, for a screen reader. */
  label: string;
  className?: string;
};

const CHALK = "#f6f8f3";

/** Where a `dot` stroke sits - the first coordinate pair in its `d`. */
function dotAt(d: string): { cx: number; cy: number } {
  const found = d.match(/-?\d+(?:\.\d+)?/g);
  return { cx: Number(found?.[0] ?? 50), cy: Number(found?.[1] ?? 50) };
}

export function ChalkDrawing({
  strokes,
  playKey,
  durationMs = 2200,
  delayMs = 0,
  label,
  className
}: ChalkDrawingProps) {
  const lines = useRef<(SVGPathElement | null)[]>([]);
  const washes = useRef<(SVGPathElement | null)[]>([]);
  const dots = useRef<(SVGCircleElement | null)[]>([]);
  const tip = useRef<SVGCircleElement | null>(null);

  // The artwork is a stable value from a lookup table, but a caller that builds
  // one inline would otherwise restart the animation on every render.
  const art = useMemo(() => strokes, [strokes]);

  useEffect(() => {
    const finish = () => {
      art.forEach((_stroke, index) => {
        const line = lines.current[index];
        if (line) line.style.strokeDashoffset = "0";
        const wash = washes.current[index];
        if (wash) wash.style.opacity = "1";
        const dot = dots.current[index];
        if (dot) dot.style.opacity = "1";
      });
      if (tip.current) tip.current.style.opacity = "0";
    };

    const still =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Measure first. A path with no measurable length - no layout engine, an
    // empty `d` - makes the whole walk meaningless, so the drawing is simply
    // shown.
    const lengths = art.map((stroke, index) => {
      if (stroke.dot) return 0;
      const line = lines.current[index];
      if (!line || typeof line.getTotalLength !== "function") return 0;
      try {
        return line.getTotalLength();
      } catch {
        return 0;
      }
    });
    const total = lengths.reduce((sum, one) => sum + one, 0);

    if (still || total <= 0) {
      finish();
      return;
    }

    // Blank board.
    art.forEach((stroke, index) => {
      const line = lines.current[index];
      if (line) {
        line.style.strokeDasharray = `${lengths[index]}`;
        line.style.strokeDashoffset = `${lengths[index]}`;
      }
      const wash = washes.current[index];
      if (wash) wash.style.opacity = "0";
      const dot = dots.current[index];
      if (dot) dot.style.opacity = "0";
    });
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
      const walked = progress * total;

      let before = 0;
      // A holder rather than a narrowed local: the chalk tip is found inside a
      // callback, and TypeScript does not follow assignments made in one.
      const chalk = { x: 0, y: 0, found: false };
      art.forEach((stroke, index) => {
        const length = lengths[index];
        const covered = Math.max(0, Math.min(length, walked - before));
        const line = lines.current[index];
        if (line) {
          line.style.strokeDashoffset = `${length - covered}`;
          if (covered > 0 && covered < length && typeof line.getPointAtLength === "function") {
            try {
              const point = line.getPointAtLength(covered);
              chalk.x = point.x;
              chalk.y = point.y;
              chalk.found = true;
            } catch {
              chalk.found = false;
            }
          }
        }
        const done = length === 0 ? walked >= before : covered >= length;
        const wash = washes.current[index];
        if (wash) wash.style.opacity = done ? "1" : "0";
        const dot = dots.current[index];
        if (dot) dot.style.opacity = done ? "1" : "0";
        before += length;
      });

      if (tip.current) {
        if (chalk.found) {
          tip.current.setAttribute("cx", `${chalk.x}`);
          tip.current.setAttribute("cy", `${chalk.y}`);
          tip.current.style.opacity = "1";
        } else {
          tip.current.style.opacity = "0";
        }
      }

      if (progress < 1) frame = requestAnimationFrame(step);
      else finish();
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [art, playKey, durationMs, delayMs]);

  return (
    <svg
      viewBox="0 0 100 100"
      role="img"
      aria-label={label}
      className={className}
      data-chalk-drawing
    >
      {/* The colour goes down first and underneath, so the outline stays the
          thing the eye follows. */}
      {art.map((stroke, index) =>
        stroke.fill && !stroke.dot ? (
          <path
            key={`wash-${index}`}
            ref={(node) => {
              washes.current[index] = node;
            }}
            d={stroke.d}
            fill={stroke.fill}
            fillOpacity={stroke.fillOpacity ?? 0.42}
            stroke="none"
            style={{ opacity: 0, transition: "opacity 320ms ease-out" }}
          />
        ) : null
      )}
      {art.map((stroke, index) =>
        stroke.dot ? (
          <circle
            key={`dot-${index}`}
            ref={(node) => {
              dots.current[index] = node;
            }}
            {...dotAt(stroke.d)}
            r={3.2}
            fill={stroke.stroke ?? CHALK}
            style={{ opacity: 0, transition: "opacity 180ms ease-out" }}
          />
        ) : (
          <path
            key={`line-${index}`}
            ref={(node) => {
              lines.current[index] = node;
            }}
            d={stroke.d}
            fill="none"
            stroke={stroke.stroke ?? CHALK}
            strokeWidth={stroke.width ?? 3.4}
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.95}
            // Hidden before the effect has measured anything. Without this the
            // whole drawing is painted once, complete, and then blanked on the
            // next frame - a flash of the answer before the answer is drawn.
            // Nothing here is longer than a few hundred units, so an offset of
            // 2000 is off the board and a zero offset is fully drawn.
            style={{ strokeDasharray: 2000, strokeDashoffset: 2000 }}
          />
        )
      )}
      {/* The chalk itself. */}
      <circle
        ref={tip}
        cx={50}
        cy={50}
        r={2.6}
        fill={CHALK}
        opacity={0}
        style={{ opacity: 0 }}
      />
    </svg>
  );
}
