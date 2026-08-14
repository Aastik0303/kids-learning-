import type { RenderableActivity } from "@/types/activity";

/**
 * The single prop contract every activity component satisfies.
 *
 * Having exactly one contract is what makes ActivityRenderer a real engine
 * rather than a switch statement with twelve bespoke call sites — a new
 * activity type only has to implement this to work everywhere.
 */
export type ActivityComponentProps = {
  activity: RenderableActivity;

  /**
   * Submit the child's answer. The renderer never decides correctness —
   * it hands the answer up, the backend evaluates, and the verdict comes
   * back down through `feedback`.
   */
  onAnswer: (answer: string, meta?: AnswerMeta) => void;

  /** Advance without answering (introduce, story, complete beats). */
  onContinue: () => void;

  /** Verdict for the current attempt, or null while unanswered. */
  feedback: ActivityFeedback | null;

  /** True while the answer is in flight — inputs should lock. */
  isSubmitting: boolean;

  /** Blocks input during a scripted guide moment. */
  isLocked: boolean;

  /** Toddler mode gets larger targets and fewer options on screen. */
  isToddlerMode: boolean;

  /** Re-reads the prompt aloud. */
  onRepeat: () => void;
};

export type AnswerMeta = {
  /** How the answer was produced — drives analytics and retry copy. */
  input: "tap" | "voice" | "draw";
  /** STT confidence, when the answer came from speech. */
  confidence?: number;
  /** Raw transcript before normalisation. */
  transcript?: string;
  /** Local stroke accuracy 0–1, for tracing activities. */
  accuracy?: number;
};

export type ActivityFeedback = {
  isCorrect: boolean;
  message: string;
  hint?: string | null;
  attempt: number;
  /** True when the backend served a different question after this attempt. */
  questionChanged: boolean;
};
