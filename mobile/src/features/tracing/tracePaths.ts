import type { Point } from "@/features/drawing/types";

/**
 * Trace targets for letters, numbers and shapes.
 *
 * Each target is stored in a 100×100 unit box and scaled to the measured
 * canvas at render time, so a trace looks right on a small phone and a
 * tablet without separate assets.
 *
 * `samples` are the points used for deterministic scoring; `path` is the
 * SVG the child sees. Keeping them separate means the visible guide can be
 * smooth while scoring stays cheap.
 */

export type TraceTarget = {
  id: string;
  label: string;
  /** SVG path in the 100×100 unit box. */
  path: string;
  /** Where the stroke should start. */
  start: Point;
  /** Sampled points along the path, for scoring. */
  samples: Point[];
  /** Number of strokes a correct form uses (informational). */
  strokeCount: number;
};

/** Sample a polyline evenly so scoring is not biased by vertex density. */
function sampleLine(points: Point[], count = 40): Point[] {
  if (points.length < 2) return points;

  const lengths: number[] = [];
  let total = 0;
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1];
    const b = points[i];
    if (!a || !b) continue;
    const segment = Math.hypot(b.x - a.x, b.y - a.y);
    lengths.push(segment);
    total += segment;
  }
  if (total === 0) return points;

  const result: Point[] = [];
  const step = total / (count - 1);
  let travelled = 0;
  let index = 0;
  let accumulated = 0;

  result.push(points[0] as Point);
  for (let s = 1; s < count; s += 1) {
    travelled = s * step;
    while (index < lengths.length && accumulated + (lengths[index] ?? 0) < travelled) {
      accumulated += lengths[index] ?? 0;
      index += 1;
    }
    const a = points[index];
    const b = points[index + 1];
    if (!a || !b) {
      result.push(points[points.length - 1] as Point);
      continue;
    }
    const segment = lengths[index] ?? 1;
    const t = segment === 0 ? 0 : (travelled - accumulated) / segment;
    result.push({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
  }
  return result;
}

function polylinePath(points: Point[]): string {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
}

function line(points: Point[], id: string, label: string, strokeCount = 1): TraceTarget {
  return {
    id,
    label,
    path: polylinePath(points),
    start: points[0] ?? { x: 50, y: 50 },
    samples: sampleLine(points),
    strokeCount,
  };
}

// ─── Shapes ─────────────────────────────────────────────────────────────

const CIRCLE_POINTS: Point[] = Array.from({ length: 33 }, (_, i) => {
  const angle = (i / 32) * Math.PI * 2 - Math.PI / 2;
  return { x: 50 + Math.cos(angle) * 38, y: 50 + Math.sin(angle) * 38 };
});

export const SHAPE_TARGETS: Record<string, TraceTarget> = {
  circle: {
    id: "circle",
    label: "Circle",
    path: `M 50 12 A 38 38 0 1 1 49.9 12`,
    start: { x: 50, y: 12 },
    samples: sampleLine(CIRCLE_POINTS),
    strokeCount: 1,
  },
  square: line(
    [
      { x: 18, y: 18 },
      { x: 82, y: 18 },
      { x: 82, y: 82 },
      { x: 18, y: 82 },
      { x: 18, y: 18 },
    ],
    "square",
    "Square",
    4,
  ),
  triangle: line(
    [
      { x: 50, y: 14 },
      { x: 86, y: 82 },
      { x: 14, y: 82 },
      { x: 50, y: 14 },
    ],
    "triangle",
    "Triangle",
    3,
  ),
  rectangle: line(
    [
      { x: 12, y: 28 },
      { x: 88, y: 28 },
      { x: 88, y: 72 },
      { x: 12, y: 72 },
      { x: 12, y: 28 },
    ],
    "rectangle",
    "Rectangle",
    4,
  ),
  star: line(
    [
      { x: 50, y: 10 },
      { x: 61, y: 40 },
      { x: 92, y: 40 },
      { x: 67, y: 59 },
      { x: 77, y: 90 },
      { x: 50, y: 71 },
      { x: 23, y: 90 },
      { x: 33, y: 59 },
      { x: 8, y: 40 },
      { x: 39, y: 40 },
      { x: 50, y: 10 },
    ],
    "star",
    "Star",
    1,
  ),
  heart: {
    id: "heart",
    label: "Heart",
    path: "M 50 84 C 14 58 18 22 40 22 C 48 22 50 30 50 34 C 50 30 52 22 60 22 C 82 22 86 58 50 84",
    start: { x: 50, y: 84 },
    samples: sampleLine([
      { x: 50, y: 84 },
      { x: 26, y: 62 },
      { x: 18, y: 38 },
      { x: 32, y: 24 },
      { x: 50, y: 34 },
      { x: 68, y: 24 },
      { x: 82, y: 38 },
      { x: 74, y: 62 },
      { x: 50, y: 84 },
    ]),
    strokeCount: 2,
  },
};

// ─── Letters and numbers ────────────────────────────────────────────────

/**
 * Simplified single-path forms. These are tracing guides for a 2–5 year
 * old, not typographic outlines — legibility of the *motion* matters more
 * than fidelity to a typeface.
 */
export const GLYPH_TARGETS: Record<string, TraceTarget> = {
  A: line([{ x: 20, y: 88 }, { x: 50, y: 12 }, { x: 80, y: 88 }], "A", "Letter A", 3),
  B: line(
    [
      { x: 28, y: 12 },
      { x: 28, y: 88 },
      { x: 64, y: 76 },
      { x: 28, y: 50 },
      { x: 64, y: 30 },
      { x: 28, y: 12 },
    ],
    "B",
    "Letter B",
    2,
  ),
  C: {
    id: "C",
    label: "Letter C",
    path: "M 76 26 A 34 38 0 1 0 76 74",
    start: { x: 76, y: 26 },
    samples: sampleLine([
      { x: 76, y: 26 },
      { x: 50, y: 14 },
      { x: 24, y: 34 },
      { x: 22, y: 56 },
      { x: 44, y: 84 },
      { x: 76, y: 74 },
    ]),
    strokeCount: 1,
  },
  D: line(
    [
      { x: 30, y: 12 },
      { x: 30, y: 88 },
      { x: 62, y: 74 },
      { x: 70, y: 50 },
      { x: 62, y: 26 },
      { x: 30, y: 12 },
    ],
    "D",
    "Letter D",
    2,
  ),
  E: line(
    [
      { x: 74, y: 14 },
      { x: 28, y: 14 },
      { x: 28, y: 50 },
      { x: 64, y: 50 },
      { x: 28, y: 50 },
      { x: 28, y: 86 },
      { x: 74, y: 86 },
    ],
    "E",
    "Letter E",
    4,
  ),
  L: line([{ x: 32, y: 12 }, { x: 32, y: 86 }, { x: 74, y: 86 }], "L", "Letter L", 2),
  O: {
    id: "O",
    label: "Letter O",
    path: "M 50 12 A 30 38 0 1 1 49.9 12",
    start: { x: 50, y: 12 },
    samples: sampleLine(
      Array.from({ length: 33 }, (_, i) => {
        const angle = (i / 32) * Math.PI * 2 - Math.PI / 2;
        return { x: 50 + Math.cos(angle) * 30, y: 50 + Math.sin(angle) * 38 };
      }),
    ),
    strokeCount: 1,
  },
  T: line([{ x: 20, y: 14 }, { x: 80, y: 14 }, { x: 50, y: 14 }, { x: 50, y: 88 }], "T", "Letter T", 2),
  1: line([{ x: 34, y: 26 }, { x: 50, y: 12 }, { x: 50, y: 88 }], "1", "Number 1", 2),
  2: line(
    [
      { x: 26, y: 28 },
      { x: 50, y: 14 },
      { x: 72, y: 30 },
      { x: 30, y: 86 },
      { x: 76, y: 86 },
    ],
    "2",
    "Number 2",
    1,
  ),
  3: line(
    [
      { x: 28, y: 18 },
      { x: 66, y: 22 },
      { x: 44, y: 48 },
      { x: 70, y: 66 },
      { x: 32, y: 86 },
    ],
    "3",
    "Number 3",
    1,
  ),
  4: line(
    [
      { x: 62, y: 88 },
      { x: 62, y: 12 },
      { x: 22, y: 62 },
      { x: 80, y: 62 },
    ],
    "4",
    "Number 4",
    2,
  ),
  5: line(
    [
      { x: 72, y: 14 },
      { x: 32, y: 14 },
      { x: 30, y: 46 },
      { x: 58, y: 46 },
      { x: 70, y: 66 },
      { x: 46, y: 86 },
      { x: 26, y: 78 },
    ],
    "5",
    "Number 5",
    2,
  ),
};

/** Resolve a concept string to a trace target, if one exists. */
export function traceTargetFor(concept: string): TraceTarget | null {
  const key = concept.trim();
  if (!key) return null;
  return (
    GLYPH_TARGETS[key.toUpperCase()] ??
    SHAPE_TARGETS[key.toLowerCase()] ??
    null
  );
}

/** Scale a unit-box target onto a measured canvas, keeping it centred. */
export function scaleTarget(
  target: TraceTarget,
  size: { width: number; height: number },
  padding = 24,
): { path: string; start: Point; samples: Point[] } {
  const available = Math.min(size.width, size.height) - padding * 2;
  const scale = Math.max(available, 1) / 100;
  const offsetX = (size.width - 100 * scale) / 2;
  const offsetY = (size.height - 100 * scale) / 2;

  const map = (point: Point): Point => ({
    x: point.x * scale + offsetX,
    y: point.y * scale + offsetY,
  });

  // The visible guide is rebuilt from the same samples used for scoring,
  // rather than transforming the authored path string. That guarantees
  // what the child traces over is exactly what gets measured — no drift
  // between the drawn curve and the scored geometry.
  const scaledSamples = target.samples.map(map);

  return {
    path: scaledSamples
      .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
      .join(" "),
    start: map(target.start),
    samples: scaledSamples,
  };
}
