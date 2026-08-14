import { distance, type Point, type Stroke, type TraceScore } from "@/features/drawing/types";

/**
 * Deterministic, on-device trace scoring (spec section 14).
 *
 * Explicitly NOT an AI judgement: stroke accuracy is geometry, and the
 * project rule is that correctness is never decided by an LLM. The guide
 * explains and encourages; this function decides whether the trace passed.
 *
 * Two independent measures, because either alone is gameable:
 *
 *   coverage  — how much of the guide path the child actually visited.
 *               Stops a single dot in the middle from scoring well.
 *   precision — how close the child's points stayed to the guide.
 *               Stops scribbling all over the canvas from scoring well.
 */

export type ScoringOptions = {
  /** How far a point may stray and still count as "on the path". */
  toleranceRadius?: number;
  /** Accuracy needed to pass. Deliberately forgiving for small hands. */
  passThreshold?: number;
  /** How near the start dot the first point must be. */
  startRadius?: number;
};

const DEFAULTS: Required<ScoringOptions> = {
  toleranceRadius: 34,
  // 0.6 is generous on purpose. A 3-year-old tracing an "A" will never
  // produce a tight line, and failing them repeatedly teaches nothing.
  passThreshold: 0.6,
  startRadius: 60,
};

export function scoreTrace(
  strokes: Stroke[],
  guideSamples: Point[],
  options: ScoringOptions = {},
): TraceScore {
  const config = { ...DEFAULTS, ...options };

  const drawn = strokes.flatMap((stroke) => stroke.points);

  if (drawn.length < 2 || guideSamples.length === 0) {
    return {
      coverage: 0,
      precision: 0,
      accuracy: 0,
      passed: false,
      startedCorrectly: false,
    };
  }

  // ── Coverage: what fraction of guide points were visited? ────────────
  let visited = 0;
  for (const sample of guideSamples) {
    const nearest = minDistance(sample, drawn);
    if (nearest <= config.toleranceRadius) visited += 1;
  }
  const coverage = visited / guideSamples.length;

  // ── Precision: how close did the child's points stay to the guide? ───
  let onPath = 0;
  for (const point of drawn) {
    const nearest = minDistance(point, guideSamples);
    if (nearest <= config.toleranceRadius) onPath += 1;
  }
  const precision = onPath / drawn.length;

  // Coverage weighted higher: finishing the shape matters more than
  // hugging the line perfectly at this age.
  const accuracy = coverage * 0.6 + precision * 0.4;

  const first = drawn[0];
  const guideStart = guideSamples[0];
  const startedCorrectly =
    !!first && !!guideStart && distance(first, guideStart) <= config.startRadius;

  return {
    coverage,
    precision,
    accuracy,
    passed: accuracy >= config.passThreshold,
    startedCorrectly,
  };
}

function minDistance(point: Point, candidates: Point[]): number {
  let best = Number.POSITIVE_INFINITY;
  for (const candidate of candidates) {
    const d = distance(point, candidate);
    if (d < best) best = d;
    // Nothing can beat zero; stop early on an exact hit.
    if (best === 0) break;
  }
  return best;
}

/**
 * Child-facing feedback for a score. Deliberately never says "wrong" —
 * a trace is always progress, and the copy reflects that.
 */
export function traceFeedback(score: TraceScore): string {
  if (score.passed && score.accuracy > 0.85) return "Beautiful tracing!";
  if (score.passed) return "You traced it! Well done!";
  if (score.coverage < 0.3) return "Let us trace along the dotted line together.";
  if (!score.startedCorrectly) return "Start at the green dot and follow the line.";
  return "Nearly there! Try following the dots.";
}
