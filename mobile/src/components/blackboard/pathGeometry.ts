/**
 * How long a path is, and how much room it takes - worked out in JavaScript.
 *
 * The web build asks the browser: `getTotalLength()` for the walk and
 * `getBBox()` for the framing. There is no layout engine behind an SVG on this
 * side - `react-native-svg` draws straight to the platform canvas and answers
 * neither question - so the geometry is measured here instead, by walking the
 * path's own commands and sampling the curves.
 *
 * Two things are wanted from it and both matter to what a child sees:
 *
 *   - **length**, because a line is revealed along its own length. Every stroke
 *     of a drawing takes a share of the time proportional to how long it is, so
 *     an estimate that is wrong by a third makes an apple's stalk take as long
 *     to draw as the apple.
 *   - **bounds**, because every artwork is written inside the same 0..100 box
 *     and each one leaves its own margin there. Drawn at its own coordinates, a
 *     circle of radius 34 arrives a third smaller than the board it was given.
 *
 * The artwork only ever uses M, L, C, A and Z, all absolute - that is what
 * `chalkArt.ts` writes and what `chalkRing` generates - so those are what this
 * understands. Anything else is skipped rather than guessed at.
 */

export type PathGeometry = {
  /** Total length in user units. 0 when nothing could be measured. */
  length: number;
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
};

/** How finely a curve is chopped up. Sixteen is well past what the eye can see
 *  at this size, and every drawing here is a handful of strokes. */
const SAMPLES = 16;

const EMPTY: PathGeometry = { length: 0, minX: 0, minY: 0, maxX: 0, maxY: 0 };

function cubicAt(p0: number, p1: number, p2: number, p3: number, t: number): number {
  const u = 1 - t;
  return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
}

/**
 * One elliptical arc, sampled.
 *
 * This is the SVG endpoint parameterisation turned into a centre and a sweep -
 * the arithmetic the specification gives in its implementation notes. It is
 * here for one caller: `chalkRing` writes a full circle as a single arc, and a
 * circle is the most common shape in the whole art library.
 */
function arcPoints(
  x0: number,
  y0: number,
  rx: number,
  ry: number,
  rotation: number,
  largeArc: boolean,
  sweep: boolean,
  x1: number,
  y1: number,
): { x: number; y: number }[] {
  if (rx === 0 || ry === 0) return [{ x: x1, y: y1 }];
  const phi = (rotation * Math.PI) / 180;
  const cos = Math.cos(phi);
  const sin = Math.sin(phi);

  const dx2 = (x0 - x1) / 2;
  const dy2 = (y0 - y1) / 2;
  const x1p = cos * dx2 + sin * dy2;
  const y1p = -sin * dx2 + cos * dy2;

  let radiusX = Math.abs(rx);
  let radiusY = Math.abs(ry);
  // A radius too small for the two endpoints is scaled up, as the spec says,
  // rather than left to produce the square root of a negative number.
  const check = (x1p * x1p) / (radiusX * radiusX) + (y1p * y1p) / (radiusY * radiusY);
  if (check > 1) {
    const grow = Math.sqrt(check);
    radiusX *= grow;
    radiusY *= grow;
  }

  const sign = largeArc === sweep ? -1 : 1;
  const numerator =
    radiusX * radiusX * radiusY * radiusY -
    radiusX * radiusX * y1p * y1p -
    radiusY * radiusY * x1p * x1p;
  const denominator = radiusX * radiusX * y1p * y1p + radiusY * radiusY * x1p * x1p;
  const coefficient =
    denominator === 0 ? 0 : sign * Math.sqrt(Math.max(0, numerator / denominator));

  const cxp = (coefficient * radiusX * y1p) / radiusY;
  const cyp = (-coefficient * radiusY * x1p) / radiusX;
  const cx = cos * cxp - sin * cyp + (x0 + x1) / 2;
  const cy = sin * cxp + cos * cyp + (y0 + y1) / 2;

  const angle = (ux: number, uy: number, vx: number, vy: number) => {
    const dot = ux * vx + uy * vy;
    const len = Math.sqrt(ux * ux + uy * uy) * Math.sqrt(vx * vx + vy * vy);
    const value = len === 0 ? 0 : Math.min(1, Math.max(-1, dot / len));
    return (ux * vy - uy * vx < 0 ? -1 : 1) * Math.acos(value);
  };

  const start = angle(1, 0, (x1p - cxp) / radiusX, (y1p - cyp) / radiusY);
  let sweepAngle = angle(
    (x1p - cxp) / radiusX,
    (y1p - cyp) / radiusY,
    (-x1p - cxp) / radiusX,
    (-y1p - cyp) / radiusY,
  );
  if (!sweep && sweepAngle > 0) sweepAngle -= 2 * Math.PI;
  if (sweep && sweepAngle < 0) sweepAngle += 2 * Math.PI;

  const points: { x: number; y: number }[] = [];
  for (let step = 1; step <= SAMPLES; step += 1) {
    const theta = start + (sweepAngle * step) / SAMPLES;
    const px = Math.cos(theta) * radiusX;
    const py = Math.sin(theta) * radiusY;
    points.push({ x: cos * px - sin * py + cx, y: sin * px + cos * py + cy });
  }
  return points;
}

/** Every command in a `d` string, with its own numbers beside it. */
function tokenise(d: string): { command: string; values: number[] }[] {
  const out: { command: string; values: number[] }[] = [];
  const pattern = /([MLCAZmlcaz])([^MLCAZmlcaz]*)/g;
  let match = pattern.exec(d);
  while (match) {
    const command = match[1] ?? "";
    const numbers = (match[2] ?? "").match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) ?? [];
    out.push({ command, values: numbers.map(Number) });
    match = pattern.exec(d);
  }
  return out;
}

export function measurePath(d: string): PathGeometry {
  const parts = tokenise(d);
  if (!parts.length) return EMPTY;

  let length = 0;
  let x = 0;
  let y = 0;
  let startX = 0;
  let startY = 0;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  const see = (px: number, py: number) => {
    if (px < minX) minX = px;
    if (py < minY) minY = py;
    if (px > maxX) maxX = px;
    if (py > maxY) maxY = py;
  };
  const lineTo = (px: number, py: number) => {
    length += Math.sqrt((px - x) * (px - x) + (py - y) * (py - y));
    x = px;
    y = py;
    see(px, py);
  };

  for (const part of parts) {
    const command = part.command.toUpperCase();
    const v = part.values;

    if (command === "M") {
      // A moveto followed by extra pairs is an implicit polyline, which is what
      // the shorthand in the artwork relies on.
      for (let index = 0; index + 1 < v.length; index += 2) {
        const px = v[index] ?? 0;
        const py = v[index + 1] ?? 0;
        if (index === 0) {
          x = px;
          y = py;
          startX = px;
          startY = py;
          see(px, py);
        } else {
          lineTo(px, py);
        }
      }
    } else if (command === "L") {
      for (let index = 0; index + 1 < v.length; index += 2) {
        lineTo(v[index] ?? 0, v[index + 1] ?? 0);
      }
    } else if (command === "C") {
      for (let index = 0; index + 5 < v.length; index += 6) {
        const x1 = v[index] ?? 0;
        const y1 = v[index + 1] ?? 0;
        const x2 = v[index + 2] ?? 0;
        const y2 = v[index + 3] ?? 0;
        const x3 = v[index + 4] ?? 0;
        const y3 = v[index + 5] ?? 0;
        const fromX = x;
        const fromY = y;
        for (let step = 1; step <= SAMPLES; step += 1) {
          const t = step / SAMPLES;
          lineTo(cubicAt(fromX, x1, x2, x3, t), cubicAt(fromY, y1, y2, y3, t));
        }
      }
    } else if (command === "A") {
      for (let index = 0; index + 6 < v.length; index += 7) {
        const points = arcPoints(
          x,
          y,
          v[index] ?? 0,
          v[index + 1] ?? 0,
          v[index + 2] ?? 0,
          (v[index + 3] ?? 0) !== 0,
          (v[index + 4] ?? 0) !== 0,
          v[index + 5] ?? 0,
          v[index + 6] ?? 0,
        );
        points.forEach((point) => lineTo(point.x, point.y));
      }
    } else if (command === "Z") {
      lineTo(startX, startY);
    }
  }

  if (minX === Infinity) return EMPTY;
  return { length, minX, minY, maxX, maxY };
}

/** Never closed in past this, or a single dot fills the board as a blot. */
const MIN_VIEW = 66;

/**
 * The view a set of strokes should be drawn through.
 *
 * Closed in on what was actually drawn - the union of every stroke, with room
 * round it for the line's own thickness. The picture's own shape is kept rather
 * than squared off, so four counters in a row take the width of a wide board
 * instead of being fitted to its height and left as a thin strip in the middle.
 */
export function viewBoxFor(
  paths: { d: string; width?: number }[],
  fallback = "0 0 100 100",
): string {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  let thickest = 3.4;

  paths.forEach((path) => {
    const box = measurePath(path.d);
    if (box.maxX < box.minX) return;
    minX = Math.min(minX, box.minX);
    minY = Math.min(minY, box.minY);
    maxX = Math.max(maxX, box.maxX);
    maxY = Math.max(maxY, box.maxY);
    thickest = Math.max(thickest, path.width ?? 3.4);
  });

  if (minX === Infinity || maxX <= minX || maxY <= minY) return fallback;

  const boxWidth = maxX - minX;
  const boxHeight = maxY - minY;
  const pad = thickest / 2 + 2 + Math.max(boxWidth, boxHeight) * 0.03;
  const grow = Math.max(1, MIN_VIEW / Math.max(boxWidth, boxHeight));
  const width = (boxWidth + pad * 2) * grow;
  const height = (boxHeight + pad * 2) * grow;
  const cx = minX + boxWidth / 2;
  const cy = minY + boxHeight / 2;
  return `${cx - width / 2} ${cy - height / 2} ${width} ${height}`;
}
