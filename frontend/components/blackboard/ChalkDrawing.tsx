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
  /**
   * What it is drawn with. `ink` is a dark line on a light card - the class
   * shows its drawings straight on the page now, with no board behind them -
   * and `chalk` is the white line a dark slate needs.
   */
  tone?: "ink" | "chalk";
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
const INK = "#25313f";

/** How strongly a colour reads. Pastel washes vanish on white. */
const WASH = { ink: 0.72, chalk: 0.42 } as const;

/** Where a `dot` stroke sits - the first coordinate pair in its `d`. */
function dotAt(d: string): { cx: number; cy: number } {
  const found = d.match(/-?\d+(?:\.\d+)?/g);
  return { cx: Number(found?.[0] ?? 50), cy: Number(found?.[1] ?? 50) };
}

export function ChalkDrawing({
  strokes,
  playKey,
  tone = "ink",
  durationMs = 2200,
  delayMs = 0,
  label,
  className
}: ChalkDrawingProps) {
  const line = tone === "chalk" ? CHALK : INK;
  const lines = useRef<(SVGPathElement | null)[]>([]);
  const washes = useRef<(SVGPathElement | null)[]>([]);
  const dots = useRef<(SVGCircleElement | null)[]>([]);
  const tip = useRef<SVGCircleElement | null>(null);

  // The artwork is a stable value from a lookup table, but a caller that builds
  // one inline would otherwise restart the animation on every render.
  const art = useMemo(() => strokes, [strokes]);

  /**
   * The drawing fills the space it is given.
   *
   * Every artwork is written inside the same 0..100 square, and each one leaves
   * its own margin there - a circle of radius 34 uses two thirds of it and a
   * square less than that. Shown at the artwork's own coordinates, the picture
   * arrives a third smaller than the box it was given, which on the board the
   * teacher holds is a small ring in the middle of a wide white screen. So the
   * view is closed in on what was actually drawn: the union of the strokes,
   * squared off so nothing is stretched, with room left round it for the line's
   * own thickness.
   *
   * It is measured, never assumed - anything without a layout engine behind it
   * keeps the plain 0..100 view - and it will not close in past `MIN_VIEW`,
   * because a single dot zoomed to fill a screen is a blot rather than a
   * drawing.
   */
  const bounds = useRef<SVGGElement | null>(null);
  const view = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const group = bounds.current;
    const svg = view.current;
    if (!group || !svg || typeof group.getBBox !== "function") return;

    const MIN_VIEW = 66;
    let box: DOMRect | { x: number; y: number; width: number; height: number };
    try {
      box = group.getBBox();
    } catch {
      return;
    }
    if (!box || box.width <= 0 || box.height <= 0) return;

    const thickest = art.reduce((most, stroke) => Math.max(most, stroke.width ?? 3.4), 3.4);
    // Half the line's own width, so a stroke on the edge is not shaved, plus a
    // margin that grows with the picture - a drawing that runs into the edge of
    // the board it is on looks like a drawing that did not fit.
    const pad = thickest / 2 + 2 + Math.max(box.width, box.height) * 0.03;
    // The view keeps the drawing's own shape rather than being squared off, so
    // a wide picture - four counters in a row - takes the width of a wide
    // board instead of being fitted to its height and left as a thin strip in
    // the middle. Nothing is stretched by it: the SVG still scales the two
    // directions together and centres what is left over.
    const grow = Math.max(1, MIN_VIEW / Math.max(box.width, box.height));
    const width = (box.width + pad * 2) * grow;
    const height = (box.height + pad * 2) * grow;
    const cx = box.x + box.width / 2;
    const cy = box.y + box.height / 2;
    svg.setAttribute("viewBox", `${cx - width / 2} ${cy - height / 2} ${width} ${height}`);
  }, [art]);

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
      ref={view}
      viewBox="0 0 100 100"
      role="img"
      aria-label={label}
      className={className}
      data-chalk-drawing
    >
      {/* Everything that was drawn, in one group, so the view above can be
          closed in on exactly what is inside it. The chalk tip is left out of
          it: it rides wherever the line has got to, and a moving thing has no
          business deciding how big the picture is. */}
      <g ref={bounds}>
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
            fillOpacity={stroke.fillOpacity ?? WASH[tone]}
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
            fill={stroke.stroke ?? line}
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
            stroke={stroke.stroke ?? line}
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
      </g>
      {/* The chalk itself. */}
      <circle
        ref={tip}
        cx={50}
        cy={50}
        r={2.6}
        fill={line}
        opacity={0}
        style={{ opacity: 0 }}
      />
    </svg>
  );
}
