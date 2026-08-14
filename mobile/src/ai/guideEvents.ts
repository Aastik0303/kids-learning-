import type { GuideEvent, GuideMode } from "@/types/guide";

/**
 * The app's own semantic events (spec section 9) and how they map onto the
 * events the backend guide agent already understands.
 *
 * Two vocabularies exist because the spec names events in product terms
 * ("LESSON_STARTED") while the backend names them in the terms the web
 * prototype used ("LEVEL_STARTED"). Mapping here keeps the backend
 * contract untouched.
 */

export type AppGuideEvent =
  | "APP_OPENED"
  | "HOME_OPENED"
  | "CLASSES_OPENED"
  | "LESSON_STARTED"
  | "QUESTION_LOADED"
  | "ANSWER_SUBMITTED"
  | "ANSWER_CORRECT"
  | "ANSWER_INCORRECT"
  | "HAND_RAISED"
  | "DOUBT_ASKED"
  | "ACTIVITY_COMPLETED"
  | "LESSON_COMPLETED"
  | "REWARDS_OPENED"
  | "HINT_REQUESTED"
  | "REPEAT_REQUESTED"
  | "CERTIFICATE_UNLOCKED";

export type EventSurface = "lesson" | "practice" | "home" | "rewards";

/**
 * Translate an app event into a backend event, given where it happened.
 * Returns null when the backend has no equivalent and no call should be
 * made at all.
 */
export function toBackendEvent(
  event: AppGuideEvent,
  surface: EventSurface,
): GuideEvent | null {
  const inPractice = surface === "practice";

  switch (event) {
    case "APP_OPENED":
      return "APP_OPENED";
    case "HOME_OPENED":
      return "HOME_OPENED";
    case "CLASSES_OPENED":
      return "ADVENTURE_OPENED";
    case "LESSON_STARTED":
      return inPractice ? "PRACTICE_STARTED" : "LEVEL_STARTED";
    case "QUESTION_LOADED":
      return inPractice ? "PRACTICE_QUESTION_LOADED" : "LEVEL_QUESTION_LOADED";
    case "ANSWER_CORRECT":
      return inPractice ? "PRACTICE_ANSWER_CORRECT" : "LEVEL_ANSWER_CORRECT";
    case "ANSWER_INCORRECT":
      return inPractice ? "PRACTICE_ANSWER_INCORRECT" : "LEVEL_ANSWER_INCORRECT";
    case "ACTIVITY_COMPLETED":
    case "LESSON_COMPLETED":
      return inPractice ? "PRACTICE_COMPLETED" : "LEVEL_COMPLETED";
    case "HAND_RAISED":
    case "DOUBT_ASKED":
      return "GUIDE_HELP_REQUESTED";
    case "HINT_REQUESTED":
      return "HINT_REQUESTED";
    case "REPEAT_REQUESTED":
      return "REPEAT_REQUESTED";
    case "REWARDS_OPENED":
      return "REWARDS_OPENED";
    case "CERTIFICATE_UNLOCKED":
      return "CERTIFICATE_UNLOCKED";
    // Purely local — the app tracks it, the agent is not consulted.
    case "ANSWER_SUBMITTED":
      return null;
  }
}

export function modeForSurface(surface: EventSurface): GuideMode {
  switch (surface) {
    case "lesson":
      return "learning";
    case "practice":
      return "practice";
    case "rewards":
      return "reward";
    case "home":
      return "navigation";
  }
}

/**
 * Whether an event is worth an LLM round-trip.
 *
 * Project rule (CLAUDE.md): the AI is for explanation, guidance, and
 * wrong-answer help. Ordinary correct answers get short static praise and
 * deterministic progression — calling the model there would add latency
 * to the single most time-sensitive moment in the app for no benefit.
 */
export function shouldCallAgent(event: AppGuideEvent, attempt: number): boolean {
  switch (event) {
    case "ANSWER_CORRECT":
      // Only celebrate through the agent when the child struggled first —
      // that is a teaching moment worth personalising.
      return attempt >= 2;
    case "ANSWER_SUBMITTED":
      return false;
    default:
      return true;
  }
}

/** Short static praise lines — no model call, no latency. */
const PRAISE = [
  "Yes! That is right!",
  "Great job!",
  "You did it!",
  "Well done!",
  "Perfect!",
  "Super!",
] as const;

export function staticPraise(seed: number): string {
  return PRAISE[Math.abs(seed) % PRAISE.length] ?? PRAISE[0];
}

const ENCOURAGEMENT = [
  "Good try! Let us look again.",
  "Almost! Try one more time.",
  "Nice try. I will help you.",
] as const;

export function staticEncouragement(seed: number): string {
  return ENCOURAGEMENT[Math.abs(seed) % ENCOURAGEMENT.length] ?? ENCOURAGEMENT[0];
}
