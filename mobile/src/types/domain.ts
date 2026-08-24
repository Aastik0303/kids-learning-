/**
 * Backend contracts, mirrored 1:1 from the FastAPI Pydantic schemas in
 * `backend/app/schemas/`. These must not drift — if a field changes here
 * without changing there, the app lies about the data it has.
 *
 * Source of truth per block is noted in the comment above it.
 */

// ─── auth.py ────────────────────────────────────────────────────────────

export type User = {
  id: string;
  name: string;
  email: string;
};

export type AuthResponse = {
  session_token: string;
  user: User;
};

export type SessionResponse = {
  user: User | null;
};

// ─── child.py ───────────────────────────────────────────────────────────

export type LearningMode = "standard" | "toddler";

export type PathProgress = {
  current_stage: number;
  completed_stages: number[];
  unlocked_stages: number[];
  score: number;
};

export type ChildProfile = {
  child_id: string;
  user_id: string;
  name: string;
  age_group: string;
  age?: number | null;
  learning_mode?: LearningMode;
  preferred_language: string;
  stars: number;
  current_path: string;
  current_stage: number;
  completed_paths: string[];
  path_progress: Record<string, PathProgress>;
  weak_skills: string[];
  rewards: string[];
  mixed_path_unlocked: boolean;
  certificate_unlocked: boolean;
};

// ─── avatar.py ──────────────────────────────────────────────────────────

export type AvatarState =
  | "idle"
  | "waving"
  | "listening"
  | "thinking"
  | "speaking"
  | "happy"
  | "celebrating"
  | "encouraging"
  | "storytelling"
  | "sleeping"
  | "error_fallback";

export type AvatarEffect =
  | "star_burst"
  | "confetti"
  | "level_unlock"
  | "reward_chest"
  | "gentle_hint"
  | "story_transition"
  | "certificate_celebration"
  | "sparkle"
  | "bounce"
  | "rainbow"
  | "pulse"
  | "none";

export type AvatarPayload = {
  state: AvatarState;
  message: string;
  speak?: boolean;
  animationEffect?: AvatarEffect | null;
  durationMs?: number | null;
};

// ─── learning.py ────────────────────────────────────────────────────────

export type PathSummary = {
  path_id: string;
  title: string;
  description: string;
  total_stages: number;
};

/** The backend's generic activity shape. `type` drives ActivityRenderer. */
export type Activity = {
  activity_id: string;
  type: string;
  prompt: string;
  visual_items: string[];
  options: string[];
  correct_answer: string;
  hint: string;
  difficulty: string;
};

export type Stage = {
  stage_id: string;
  path_id: string;
  stage_number: number;
  title: string;
  objective: string;
  module_type: string;
  difficulty: string;
  intro_message: string;
  passing_score: number;
  star_reward: number;
  activities: Activity[];
  next_stage: number | null;
};

export type LearningResponse = {
  session_id: string;
  child_id: string;
  path_id: string;
  stage_number: number;
  tutor_response: string;
  activity: Activity | null;
  is_correct: boolean | null;
  attempt_number: number;
  feedback: string;
  stars_earned: number;
  current_score: number;
  stage_completed: boolean;
  next_stage_unlocked: boolean;
  recommended_practice: boolean;
  question_changed: boolean;
  complete: boolean;
  avatar?: AvatarPayload | null;
};

// ─── practice.py ────────────────────────────────────────────────────────

export type PracticeTopic = {
  topic: string;
  title: string;
  unlocked: boolean;
};

export type PracticeStartResponse = {
  practice_session_id: string;
  topic: string;
  activities: Activity[];
  selection_reason: string;
};

export type PracticeAnswerResponse = {
  is_correct: boolean;
  feedback: string;
  hint?: string | null;
  attempt_number: number;
  question_changed: boolean;
  avatar?: AvatarPayload | null;
};

// ─── progress.py ────────────────────────────────────────────────────────

export type ProgressResponse = {
  child: ChildProfile;
};

export type RewardsResponse = {
  stars: number;
  rewards: string[];
};

export type CertificateResponse = {
  unlocked: boolean;
  certificate_id?: string | null;
  child_name?: string | null;
  title: string;
  completion_message?: string | null;
  completion_date?: string | null;
  stars_earned: number;
  celebration_line: string;
};

// ─── history.py ─────────────────────────────────────────────────────────

export type ActivityAttempt = {
  id: string;
  child_id: string;
  session_id: string;
  activity_id: string;
  topic: string;
  skill: string;
  level_id?: string | null;
  child_answer: string;
  is_correct: boolean;
  attempt_number: number;
  created_at: string;
};

export type HistoryResponse = {
  child_id: string;
  attempts: ActivityAttempt[];
};

// ─── toddler.py ─────────────────────────────────────────────────────────

export type ToddlerModule = "alphabets" | "numbers" | "colours" | "shapes";

export type ToddlerActivityType =
  | "introduce"
  | "repeat_after_me"
  | "recognition"
  | "count_objects"
  | "complete";

export type ToddlerActivity = {
  activity_id: string;
  type: ToddlerActivityType;
  prompt: string;
  speech: string;
  concept: string;
  emoji: string;
  word?: string | null;
  visual_items: string[];
  choices: string[];
  answer?: string | null;
  accepted: string[];
};

export type ToddlerLevel = {
  id: string;
  mode: "toddler";
  module: ToddlerModule;
  level: number;
  title: string;
  concepts: string[];
  star_reward: number;
  activities: ToddlerActivity[];
};

export type ToddlerModuleSummary = {
  module: ToddlerModule;
  title: string;
  icon: string;
  levels: number;
};

export type SpeechEvaluation = {
  result: "correct" | "close" | "retry" | "unclear";
  confidence: number;
  expected: string;
  heard: string;
  retry: boolean;
};

export type ToddlerGuideResponse = {
  speech: string;
  emotion: "happy" | "encouraging" | "thinking" | "celebrate" | "gentle_retry";
  emoji: string;
  action:
    | "speak"
    | "listen"
    | "repeat"
    | "next_activity"
    | "show_visual"
    | "give_reward"
    | "complete_level";
  repeat: boolean;
  target: string | null;
};

export type ToddlerResponse = {
  session_id: string;
  child_id: string;
  module: ToddlerModule;
  level: number;
  activity: ToddlerActivity | null;
  guide: ToddlerGuideResponse;
  evaluation: SpeechEvaluation | null;
  stars_earned: number;
  total_stars: number;
  attempt_count: number;
  completed_activities: string[];
  level_completed: boolean;
  next_level_unlocked: boolean;
  question_changed: boolean;
  learned_concepts: string[];
  avatar: AvatarPayload;
};

// ─── speech.py ──────────────────────────────────────────────────────────

/** Stage 1 of the child speech pipeline — `child_speech_service.py`.
 *
 * Says what the child most likely said, never whether it was right.
 * `retry_suggested` means ask them to say it again; it is not a wrong answer. */
export type ChildSpeechResult = {
  token: string;
  confidence: number;
  status: "resolved" | "needs_enhancement" | "retry" | "empty";
  reason_code: string;
  self_corrected: boolean;
  needs_enhancement: boolean;
  retry_suggested: boolean;
};

/** Response of POST /speech/normalize — `answer_resolution_service.py`. */
export type AnswerResolutionResult = {
  raw_transcript: string;
  normalized: string;
  resolved_answer: string;
  resolution_confidence: number;
  ambiguous: boolean;
  matched_candidate?: string | null;
  input_kind: "answer" | "unresolved" | "empty";
  child_speech?: ChildSpeechResult | null;
};

/** Request body of POST /speech/normalize. */
export type SpeechNormalizeRequest = {
  transcript: string;
  confidence: number;
  answer_type?: string;
  activity_id?: string | null;
  correct_answer?: string | null;
  accepted_answers?: string[];
  options?: string[];
};

// ─── common.py ──────────────────────────────────────────────────────────

export type ApiErrorBody = {
  error?: {
    code: string;
    message: string;
  };
};
