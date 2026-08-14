/**
 * Guide Agent contracts, mirrored from `backend/app/schemas/guide.py`.
 *
 * The backend is the authority on which events, actions and visual actions
 * exist. Everything the LLM may emit is a closed union here on purpose —
 * that is what makes the allowlist validation in `ai/guideSchema.ts`
 * exhaustive rather than best-effort.
 */

import type { AvatarPayload } from "@/types/domain";

export type GuideMode =
  | "welcome"
  | "navigation"
  | "learning"
  | "practice"
  | "help"
  | "reward"
  | "parent_help";

/** Events the backend already understands. */
export const BACKEND_GUIDE_EVENTS = [
  "APP_OPENED",
  "HOME_OPENED",
  "PRACTICE_OPENED",
  "PRACTICE_STARTED",
  "PRACTICE_QUESTION_LOADED",
  "PRACTICE_ANSWER_CORRECT",
  "PRACTICE_ANSWER_INCORRECT",
  "PRACTICE_COMPLETED",
  "ADVENTURE_OPENED",
  "LEVEL_OPENED",
  "LEVEL_STARTED",
  "LEVEL_QUESTION_LOADED",
  "LEVEL_ANSWER_CORRECT",
  "LEVEL_ANSWER_INCORRECT",
  "LEVEL_COMPLETED",
  "WORLD_COMPLETED",
  "WORLD_UNLOCKED",
  "REWARDS_OPENED",
  "CERTIFICATE_UNLOCKED",
  "GUIDE_HELP_REQUESTED",
  "HINT_REQUESTED",
  "REPEAT_REQUESTED",
] as const;

export type GuideEvent = (typeof BACKEND_GUIDE_EVENTS)[number];

export const GUIDE_ACTION_TYPES = [
  "none",
  "highlight",
  "scroll_to",
  "open_safe_route",
  "show_tooltip",
  "repeat_instruction",
  "show_hint",
  "wait_for_click",
] as const;

export type GuideActionType = (typeof GUIDE_ACTION_TYPES)[number];

export const GUIDE_VISUAL_ACTION_TYPES = [
  "none",
  "pulse",
  "highlight",
  "highlight_sequence",
  "dim_others",
  "group_objects",
  "trace_shape",
  "show_example",
] as const;

export type GuideVisualActionType = (typeof GUIDE_VISUAL_ACTION_TYPES)[number];

export const GUIDE_STRATEGIES = [
  "welcome",
  "navigation",
  "read_question",
  "visual_explanation",
  "hint",
  "re_explain",
  "celebrate",
  "help",
  "none",
] as const;

export type GuideStrategy = (typeof GUIDE_STRATEGIES)[number];

export type GuideConversationTurn = {
  role: "user" | "assistant";
  content: string;
};

export type GuideQuestionContext = {
  activity_id: string;
  topic?: string | null;
  concept?: string | null;
  learning_objective?: string | null;
  prompt: string;
  answer_type?: string | null;
  options?: string[];
  correct_answer?: string | null;
  child_answer?: string | null;
  attempt?: number;
  hint?: string | null;
  visual_items?: string[];
  accepted_answers?: string[];
  recent_answers?: string[];
  example?: string | null;
  difficulty?: string | null;
};

export type GuideProgressContext = {
  current_world?: string | null;
  current_level?: string | null;
  last_completed_level?: string | null;
  last_completed_title?: string | null;
  last_completed_objective?: string | null;
  last_completed_at?: string | null;
  weak_skills?: string[];
  session_stars?: number;
};

export type ToddlerGuideContext = {
  learning_mode: string;
  age?: number | null;
  module?: string | null;
  level?: number | null;
  concept?: string | null;
  activity_type?: string | null;
  expected_answer?: string | null;
  recognized_speech?: string | null;
  attempt_count?: number;
  stars?: number;
  recent_result?: string | null;
};

export type GuideRequest = {
  session_id?: string | null;
  child_id?: string | null;
  mode: GuideMode;
  event: GuideEvent;
  route: string;
  screen: string;
  feature: string;
  age_group?: string;
  age?: number | null;
  learning_mode?: string;
  preferred_language?: string;
  conversation?: GuideConversationTurn[];
  question?: GuideQuestionContext | null;
  progress?: GuideProgressContext | null;
  toddler?: ToddlerGuideContext | null;
  available_actions: GuideActionType[];
  available_targets: string[];
  allowed_visual_targets?: string[];
};

export type GuideUiAction = {
  type: GuideActionType;
  target: string | null;
};

export type GuideVisualAction = {
  type: GuideVisualActionType;
  targets: string[];
};

export type GuideResponse = {
  message: string;
  strategy: GuideStrategy;
  avatar: AvatarPayload;
  ui_action: GuideUiAction;
  visual_action: GuideVisualAction;
  next_expected_event: string;
};
