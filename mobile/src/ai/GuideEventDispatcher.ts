import { modeForSurface, toBackendEvent, type AppGuideEvent, type EventSurface } from "@/ai/guideEvents";
import type { RenderableActivity } from "@/types/activity";
import type { ChildProfile } from "@/types/domain";
import type {
  GuideActionType,
  GuideConversationTurn,
  GuideQuestionContext,
  GuideRequest,
} from "@/types/guide";

/**
 * Builds the payload sent to POST /agent/guide.
 *
 * Everything the agent is allowed to know and allowed to do is declared
 * here: the visible question, compact progress, and the exact action and
 * target allowlists for the current screen. The agent cannot act outside
 * what this payload offers, because `guideSchema.ts` validates its reply
 * against these same lists.
 *
 * Visible question data is passed inline rather than retrieved — question
 * explanation deliberately does not use RAG (see README).
 */

export type DispatchContext = {
  event: AppGuideEvent;
  surface: EventSurface;
  child: ChildProfile | null;
  sessionId: string | null;
  routeName: string;
  screen: string;
  feature: string;
  activity: RenderableActivity | null;
  attempt: number;
  childAnswer: string | null;
  recentAnswers: string[];
  sessionStars: number;
  pathId: string | null;
  stageNumber: number | null;
  conversation: GuideConversationTurn[];
  /** Registered target ids currently on screen. */
  availableTargets: readonly string[];
  availableVisualTargets: readonly string[];
  /** Actions this screen is prepared to honour. */
  offeredActions: readonly GuideActionType[];
};

/** Default action set for a screen with no interactive activity. */
export const NAVIGATION_ACTIONS: readonly GuideActionType[] = [
  "none",
  "highlight",
  "scroll_to",
  "open_safe_route",
  "show_tooltip",
];

/** Action set while a question is on screen. Navigation is excluded on
 * purpose — the agent must not pull a child out of a lesson mid-question. */
export const LESSON_ACTIONS: readonly GuideActionType[] = [
  "none",
  "highlight",
  "scroll_to",
  "show_tooltip",
  "show_hint",
  "repeat_instruction",
  "wait_for_click",
];

function questionContext(
  activity: RenderableActivity | null,
  attempt: number,
  childAnswer: string | null,
  recentAnswers: string[],
): GuideQuestionContext | null {
  if (!activity) return null;

  return {
    activity_id: activity.id,
    topic: activity.concept || null,
    concept: activity.concept || null,
    learning_objective: null,
    prompt: activity.prompt,
    answer_type: activity.kind,
    options: activity.options,
    // The correct answer is sent so the agent can *explain* it. It never
    // decides correctness — `learning_service.py` already did that.
    correct_answer: activity.correctAnswer || null,
    child_answer: childAnswer,
    attempt,
    hint: activity.hint || null,
    visual_items: activity.visualItems,
    accepted_answers: activity.acceptedAnswers,
    recent_answers: recentAnswers,
    example: null,
    difficulty: activity.difficulty || null,
  };
}

export function buildGuideRequest(context: DispatchContext): GuideRequest | null {
  const backendEvent = toBackendEvent(context.event, context.surface);
  if (!backendEvent) return null;

  const child = context.child;

  return {
    session_id: context.sessionId,
    child_id: child?.child_id ?? null,
    mode: modeForSurface(context.surface),
    event: backendEvent,
    route: context.routeName,
    screen: context.screen,
    feature: context.feature,
    age_group: child?.age_group ?? "3-6",
    age: child?.age ?? null,
    learning_mode: child?.learning_mode ?? "standard",
    preferred_language: child?.preferred_language ?? "English",
    conversation: context.conversation.slice(-8),
    question: questionContext(
      context.activity,
      context.attempt,
      context.childAnswer,
      context.recentAnswers,
    ),
    progress: {
      current_world: context.pathId,
      current_level: context.stageNumber ? String(context.stageNumber) : null,
      last_completed_level: null,
      weak_skills: child?.weak_skills ?? [],
      session_stars: context.sessionStars,
    },
    toddler:
      child?.learning_mode === "toddler"
        ? {
            learning_mode: "toddler",
            age: child.age ?? null,
            module: context.pathId,
            level: context.stageNumber,
            concept: context.activity?.concept ?? null,
            activity_type: context.activity?.kind ?? null,
            expected_answer: context.activity?.correctAnswer ?? null,
            recognized_speech: context.childAnswer,
            attempt_count: context.attempt,
            stars: child.stars,
            recent_result: null,
          }
        : null,
    available_actions: [...context.offeredActions],
    available_targets: [...context.availableTargets],
    allowed_visual_targets: [...context.availableVisualTargets],
  };
}
