/**
 * Backend contracts, mirrored 1:1 from the FastAPI Pydantic schemas in
 * `backend/app/schemas/`. These must not drift — if a field changes here
 * without changing there, the app lies about the data it has.
 *
 * Source of truth per block is noted in the comment above it.
 */

import type { GuideVisualAction } from "@/types/guide";

// ─── auth.py ────────────────────────────────────────────────────────────

export type User = {
  id: string;
  name: string;
  email: string;
};

/**
 * What `POST /auth/login` answers when the password was right and a code has
 * been emailed. No session in it, and nothing here can be turned into one -
 * `POST /auth/otp/verify` is what mints the token.
 */
export type SignInChallenge = {
  otp_required: true;
  challenge_id: string;
  /** Enough of the address to recognise, never the whole of it. */
  email_hint: string;
  expires_in: number;
  resend_after: number;
  /** Development machines with no mailer only. */
  dev_code: string | null;
};

export type LoginResult = AuthResponse | SignInChallenge;

export function isSignInChallenge(result: LoginResult): result is SignInChallenge {
  return (result as SignInChallenge).otp_required === true;
}

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

/** One subject's standing, as `/progress` and `/children` send it back. */
export type SubjectProgress = {
  completed_topics: string[];
  unlocked_topics: string[];
  current_topic_id: string | null;
  scores: Record<string, number>;
};

/**
 * A child, as the server sends one.
 *
 * The fields are in two groups and it is worth knowing which is which. The
 * **curriculum** fields below - `class_id`, `subject_progress` and the rest -
 * are what `app/schemas/child.py` actually returns today, and they are what the
 * class and the Adventure board read.
 *
 * The **path** fields above them (`age_group`, `current_path`, `path_progress`,
 * `completed_paths`) are from the older paths-and-stages model that the picked-
 * lesson screens were built on. The server no longer sends several of them, so
 * they are optional here rather than promised: a type that swears a field is
 * there when the API stopped sending it is worse than one that admits the gap.
 */
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

  // ── The curriculum shape the server sends now ──────────────────────────
  /** Which class the child is in - what they see, override included. */
  class_id?: string;
  default_class_id?: string;
  class_override?: string | null;
  experience_mode?: string;
  birth_year?: number;
  birth_month?: number;
  age_years?: number;
  current_subject_id?: string | null;
  current_topic_id?: string | null;
  completed_subjects?: string[];
  /**
   * What is finished and what is open, per subject. The Adventure board reads
   * this and nothing else for three of its four standings; today's frozen plan
   * supplies the fourth.
   */
  subject_progress?: Record<string, SubjectProgress>;
};

// ─── avatar.py ──────────────────────────────────────────────────────────

/**
 * What the avatar's face is doing.
 *
 * The first eleven are the states `avatar.py` sends. The last four are the
 * class's own and are decided on the device by `avatarMoodForTeacher`: the AI
 * Teacher is the one screen where a child cannot read a word, so the panda's
 * face has to carry the verdict, and eleven feelings were not enough to tell
 * "well done" from "I am pleased with the whole of that" or a microphone that
 * heard nothing from a class that could not carry on.
 *
 * `sad` and `crying` are **never** shown for a wrong answer. They are for when
 * the *app* has let the child down; a four-year-old who makes the panda cry by
 * getting a letter wrong learns to stop answering.
 */
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
  | "error_fallback"
  | "proud"
  | "curious"
  | "sad"
  | "crying";

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
  /** The recogniser's runners-up, best first. At most five are read. */
  alternatives?: string[];
};

// ─── common.py ──────────────────────────────────────────────────────────

export type ApiErrorBody = {
  error?: {
    code: string;
    message: string;
  };
};

// ─── conductor.py ───────────────────────────────────────────────────────

/**
 * The conductor's one response shape. The class is run server-side and this
 * is the whole of what the client is told about the current beat: what to
 * show, what to say, what to wait for, and what to report when nothing comes.
 *
 * The client renders this and reports what the child did. It decides nothing —
 * not whether an answer was right, not what comes next, and not what silence
 * means.
 */
export type ConductorPhase =
  | "greet"
  | "set"
  | "i_do"
  | "say_it"
  | "we_do"
  | "you_do"
  | "check"
  | "branch"
  | "close";

export type ConductorInputKind = "tap" | "voice" | "trace" | "idle" | "doubt" | "ready";

export type ConductorScaffold = {
  level: number;
  point_at: string[];
  dim_others: boolean;
  demo_tap: boolean;
  /** Already trimmed server-side. The client may not add to or trim this. */
  options_shown: string[];
  co_narrate: string;
};

export type ConductorPresentation = {
  choices_shown: number;
  touch_target_px: number;
  text_density: string;
  decoration: string;
  motion: string;
  narration_speed: number;
};

export type ConductorSpeech = {
  text: string;
  language: string;
  speak: boolean;
  voice_speed: number;
  source: "template" | "llm";
};

export type ConductorNextInput = {
  expects: ConductorInputKind;
  timeout_ms: number;
  on_timeout: ConductorInputKind;
};

/** Set whenever the microphone should be open for this turn. */
export type ConductorListen = {
  active: boolean;
  /** The thing the child is being asked to say, e.g. "A" or "अ". */
  expect: string;
  contextual_strings: string[];
  language: string;
  attempt: number;
  max_attempts: number;
  hold_open_ms: number;
};

export type ConductorProgress = { shape: string; filled: number; total: number };

export type ConductorClose = {
  reason: "completed" | "day_complete" | "end_kindly" | "paused" | "session_overrun";
  stars_earned: number;
  topic_completed: boolean;
  revisit_skill_id: string | null;
};

/**
 * The conductor's activity. Same shape as `Activity`, with two differences
 * that matter: `correct_answer` is **always null** — the answer key never
 * leaves the server during a class — and `accept` carries the extra spellings
 * a spoken answer may arrive in.
 */
export type ConductorActivity = Omit<Activity, "correct_answer"> & {
  correct_answer: string | null;
  accept: string[];
  answer_kind: string;
  skill_id?: string | null;
  trace_target?: string | null;
  open_ended?: boolean;
};

export type ConductorDirective = {
  session_id: string;
  child_id: string;
  topic_id: string;
  phase: ConductorPhase;
  activity: ConductorActivity | null;
  scaffold: ConductorScaffold;
  presentation: ConductorPresentation;
  speech: ConductorSpeech;
  avatar: AvatarPayload;
  visual_action: GuideVisualAction;
  next_input: ConductorNextInput;
  listen: ConductorListen;
  progress: ConductorProgress;
  /** Set when the guide is talking and nothing is expected of the child. */
  auto_advance_in_ms: number | null;
  close: ConductorClose | null;
  branch: string | null;
  teaching_strategy: string | null;
  /** What an utterance that was not an answer was taken to be. Diagnostics. */
  heard_as: string | null;
};

export type ConductorInputPayload = {
  kind: ConductorInputKind;
  answer?: string;
  latency_ms?: number;
  confidence?: number;
  alternatives?: string[];
};
