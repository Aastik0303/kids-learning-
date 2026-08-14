export type Point = { x: number; y: number };

export type Stroke = {
  id: string;
  points: Point[];
  color: string;
  width: number;
};

/** Result of comparing drawn strokes against a target path. */
export type TraceScore = {
  /** 0–1 fraction of the guide path the child actually covered. */
  coverage: number;
  /** 0–1, how closely the strokes hugged the guide path. */
  precision: number;
  /** Combined 0–1 score used for the pass threshold. */
  accuracy: number;
  /** True when the trace is good enough to count as done. */
  passed: boolean;
  /** Whether the child started near the marked start point. */
  startedCorrectly: boolean;
};

/** Converts a point list into an SVG path string. */
export function toSvgPath(points: Point[]): string {
  if (points.length === 0) return "";
  const [first, ...rest] = points;
  if (!first) return "";

  // Quadratic smoothing through midpoints keeps a child's shaky line
  // looking like a confident stroke.
  let path = `M ${first.x.toFixed(2)} ${first.y.toFixed(2)}`;
  for (let i = 0; i < rest.length; i += 1) {
    const point = rest[i];
    const previous = i === 0 ? first : rest[i - 1];
    if (!point || !previous) continue;
    const midX = (previous.x + point.x) / 2;
    const midY = (previous.y + point.y) / 2;
    path += ` Q ${previous.x.toFixed(2)} ${previous.y.toFixed(2)} ${midX.toFixed(2)} ${midY.toFixed(2)}`;
  }
  const last = rest[rest.length - 1];
  if (last) path += ` L ${last.x.toFixed(2)} ${last.y.toFixed(2)}`;
  return path;
}

export function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}
