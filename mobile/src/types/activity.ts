/**
 * The ActivityRenderer's own vocabulary (spec section 7) plus the adapter
 * that maps real backend activity types onto it.
 *
 * Why an adapter: the backend curriculum emits 18 distinct `type` strings
 * ("multiple_choice", "identify_colour", "select_letter", …) that predate
 * this renderer. Rather than rename them — which would break the deterministic
 * answer-checking and scoring services — we translate at the boundary.
 * Backend contracts stay untouched; new mobile-only kinds slot in beside them.
 */

import type { Activity, ConductorActivity, ToddlerActivity } from "@/types/domain";

/** Every activity the renderer knows how to draw. */
export const ACTIVITY_KINDS = [
  // Spoken
  "voice_repeat",
  "sentence_repeat",
  // Tap / select
  "tap_choice",
  "image_match",
  "count_objects",
  "shape_match",
  "color_match",
  "word_build",
  // Draw / trace
  "letter_trace",
  "shape_trace",
  "free_draw",
  // Passive / narrative
  "story_listen",
  // Teaching + closing beats the backend already emits
  "introduce",
  "complete",
] as const;

export type ActivityKind = (typeof ACTIVITY_KINDS)[number];

/** How the child is expected to answer — drives the input affordance. */
export type AnswerMode = "voice" | "tap" | "draw" | "none";

export const ANSWER_MODE_BY_KIND: Record<ActivityKind, AnswerMode> = {
  voice_repeat: "voice",
  sentence_repeat: "voice",
  tap_choice: "tap",
  image_match: "tap",
  count_objects: "tap",
  shape_match: "tap",
  color_match: "tap",
  word_build: "tap",
  letter_trace: "draw",
  shape_trace: "draw",
  free_draw: "draw",
  story_listen: "none",
  introduce: "none",
  complete: "none",
};

/**
 * Backend `Activity.type` → renderer kind.
 * Values on the left are the real strings found in
 * `backend/app/data/*_path.json`.
 */
const STANDARD_KIND_MAP: Record<string, ActivityKind> = {
  // Choice-shaped
  multiple_choice: "tap_choice",
  select_letter: "tap_choice",
  select_number: "tap_choice",
  mixed: "tap_choice",
  // Matching
  match: "image_match",
  // Domain-specific recognition
  identify_colour: "color_match",
  recognize_colour: "color_match",
  identify_shape: "shape_match",
  recognize_shape: "shape_match",
  // Counting
  count_objects: "count_objects",
  // Spoken repetition
  repeat_letter: "voice_repeat",
  repeat_number: "voice_repeat",
  repeat_colour: "voice_repeat",
  repeat_shape: "voice_repeat",
  // Teaching beats
  introduce_letter: "introduce",
  introduce_number: "introduce",
  introduce_colour: "introduce",
  introduce_shape: "introduce",
};

/** Toddler `ToddlerActivity.type` → renderer kind. */
const TODDLER_KIND_MAP: Record<ToddlerActivity["type"], ActivityKind> = {
  introduce: "introduce",
  repeat_after_me: "voice_repeat",
  recognition: "tap_choice",
  count_objects: "count_objects",
  complete: "complete",
};

/**
 * Resolve an unknown backend type. Falls back on shape rather than
 * throwing — an unrecognised activity must still be answerable, because
 * a curriculum update should never hard-crash a child mid-lesson.
 */
export function resolveActivityKind(activity: Activity): ActivityKind {
  const mapped = STANDARD_KIND_MAP[activity.type];
  if (mapped) return mapped;

  if (activity.options.length > 0) return "tap_choice";
  if (activity.visual_items.length > 0) return "count_objects";
  return "introduce";
}

export function resolveToddlerActivityKind(activity: ToddlerActivity): ActivityKind {
  return TODDLER_KIND_MAP[activity.type] ?? "introduce";
}

/**
 * Normalised activity the renderer actually consumes. Both the standard
 * and toddler backend shapes collapse into this, so every activity
 * component has exactly one prop contract to satisfy.
 */
export type RenderableActivity = {
  id: string;
  kind: ActivityKind;
  answerMode: AnswerMode;
  /** Text shown on screen. */
  prompt: string;
  /** Text the guide speaks. Falls back to `prompt`. */
  speech: string;
  /** Emoji/character tiles to display and count. */
  visualItems: string[];
  /** Tappable answer options. */
  options: string[];
  /** Deterministic correct answer — never inferred by the LLM. */
  correctAnswer: string;
  /** Additional strings the backend will accept as correct. */
  acceptedAnswers: string[];
  hint: string;
  difficulty: string;
  /** Single concept under teaching, e.g. "A", "3", "red", "triangle". */
  concept: string;
  /** Large display glyph for introduce/trace activities. */
  glyph: string;
  /** Word being built or read, when relevant. */
  word?: string | null;
  /** Origin, so the screen knows which API to answer against. */
  source: "standard" | "toddler" | "local";
};

export function toRenderableActivity(activity: Activity): RenderableActivity {
  const kind = resolveActivityKind(activity);
  return {
    id: activity.activity_id,
    kind,
    answerMode: ANSWER_MODE_BY_KIND[kind],
    prompt: activity.prompt,
    speech: activity.prompt,
    visualItems: activity.visual_items,
    options: activity.options,
    correctAnswer: activity.correct_answer,
    acceptedAnswers: [],
    hint: activity.hint,
    difficulty: activity.difficulty,
    concept: activity.correct_answer,
    glyph: activity.visual_items[0] ?? activity.correct_answer,
    source: "standard",
  };
}

export function toddlerToRenderableActivity(activity: ToddlerActivity): RenderableActivity {
  const kind = resolveToddlerActivityKind(activity);
  return {
    id: activity.activity_id,
    kind,
    answerMode: ANSWER_MODE_BY_KIND[kind],
    prompt: activity.prompt,
    speech: activity.speech || activity.prompt,
    visualItems: activity.visual_items,
    options: activity.choices,
    correctAnswer: activity.answer ?? "",
    acceptedAnswers: activity.accepted,
    hint: "",
    difficulty: "easy",
    concept: activity.concept,
    glyph: activity.emoji || activity.concept,
    word: activity.word,
    source: "toddler",
  };
}

/**
 * A conductor directive's activity, ready to render.
 *
 * Two things differ from `toRenderableActivity`. The answer key is absent by
 * design — the conductor never sends it — so `correctAnswer` is empty and the
 * renderer must not look for it. And the options come from the directive's
 * **scaffold**, already trimmed server-side for this child on this attempt:
 * the client may not widen that list, so it is passed in rather than read off
 * the activity.
 */
export function conductorToRenderableActivity(
  activity: ConductorActivity,
  optionsShown: string[],
): RenderableActivity {
  const kind = resolveActivityKind({ ...activity, correct_answer: "" });
  const glyph = activity.visual_items[0] ?? activity.trace_target ?? "";
  return {
    id: activity.activity_id,
    kind,
    answerMode: ANSWER_MODE_BY_KIND[kind],
    prompt: activity.prompt,
    // The guide's line is spoken from the directive's own speech block, not
    // from the prompt — on a Hindi level the prompt is Devanagari and what is
    // *said* is an English sentence with the letter quoted inside it.
    speech: "",
    visualItems: activity.visual_items,
    options: optionsShown.length > 0 ? optionsShown : activity.options,
    correctAnswer: "",
    acceptedAnswers: activity.accept ?? [],
    hint: activity.hint,
    difficulty: activity.difficulty,
    concept: glyph,
    glyph,
    source: "standard",
  };
}
