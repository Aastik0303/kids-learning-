export type User = {
  id: string;
  name: string;
  email: string;
};

export type AuthResponse = {
  session_token: string;
  user: User;
};

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
  learning_mode?: "standard" | "toddler";
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

export type PathSummary = {
  path_id: string;
  title: string;
  description: string;
  total_stages: number;
};

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
  complete: boolean;
  avatar?: import("@/components/avatar/avatar.types").AvatarPayload | null;
};

export type GuidanceAction =
  | "highlight_element"
  | "scroll_to_element"
  | "open_safe_route"
  | "show_tooltip"
  | "show_next_step"
  | "repeat_instruction"
  | "show_hint"
  | "wait_for_child_click"
  | "dismiss_guide"
  | "open_current_stage"
  | "open_practice"
  | "open_rewards"
  | "open_parent_profile"
  | "go_home";

export type GuidancePayload = {
  action: GuidanceAction;
  target_id: string | null;
  wait_for_child_click: boolean;
};

export type GuideMode = "welcome" | "navigation" | "learning" | "practice" | "help" | "reward" | "parent_help";

export type GuideEvent =
  | "APP_OPENED"
  | "HOME_OPENED"
  | "PRACTICE_OPENED"
  | "PRACTICE_STARTED"
  | "PRACTICE_QUESTION_LOADED"
  | "PRACTICE_ANSWER_CORRECT"
  | "PRACTICE_ANSWER_INCORRECT"
  | "PRACTICE_COMPLETED"
  | "ADVENTURE_OPENED"
  | "LEVEL_OPENED"
  | "LEVEL_STARTED"
  | "LEVEL_QUESTION_LOADED"
  | "LEVEL_ANSWER_CORRECT"
  | "LEVEL_ANSWER_INCORRECT"
  | "LEVEL_COMPLETED"
  | "WORLD_COMPLETED"
  | "WORLD_UNLOCKED"
  | "REWARDS_OPENED"
  | "CERTIFICATE_UNLOCKED"
  | "GUIDE_HELP_REQUESTED"
  | "HINT_REQUESTED"
  | "REPEAT_REQUESTED";

export type GuideActionType = "none" | "highlight" | "scroll_to" | "open_safe_route" | "show_tooltip" | "repeat_instruction" | "show_hint" | "wait_for_click";

export type GuideQuestionContext = {
  activity_id: string;
  topic?: string | null;
  concept?: string | null;
  prompt: string;
  options: string[];
  correct_answer?: string | null;
  child_answer?: string | null;
  attempt: number;
  hint?: string | null;
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
  learning_mode?: "standard" | "toddler";
  preferred_language?: string;
  toddler?: {
    learning_mode: "standard" | "toddler";
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
  } | null;
  question?: GuideQuestionContext | null;
  progress?: {
    current_world?: string | null;
    current_level?: string | null;
    last_completed_level?: string | null;
    weak_skills?: string[];
    session_stars?: number;
  } | null;
  available_actions: GuideActionType[];
  available_targets: string[];
};

export type GuideResponse = {
  message: string;
  strategy: "welcome" | "navigation" | "read_question" | "hint" | "re_explain" | "celebrate" | "help" | "none";
  avatar: import("@/components/avatar/avatar.types").AvatarPayload;
  ui_action: {
    type: GuideActionType;
    target: string | null;
  };
  next_expected_event: string;
};

export type CompanionResponse = {
  request_id: string;
  session_id: string;
  mode: string;
  message: string;
  avatar: import("@/components/avatar/avatar.types").AvatarPayload;
  guidance: GuidancePayload;
  next_action: string;
  recommendation: {
    kind?: string;
    path_id?: string | null;
    stage_number?: number | null;
    target_id?: string | null;
    route?: string;
    label?: string;
  };
};

export type LearningMode = "standard" | "toddler";

export type ToddlerModule = "alphabets" | "numbers" | "colours" | "shapes";

export type ToddlerActivity = {
  activity_id: string;
  type: "introduce" | "repeat_after_me" | "recognition" | "count_objects" | "complete";
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
  action: "speak" | "listen" | "repeat" | "next_activity" | "show_visual" | "give_reward" | "complete_level";
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
  learned_concepts: string[];
  avatar: import("@/components/avatar/avatar.types").AvatarPayload;
};

export type ToddlerModuleSummary = {
  module: ToddlerModule;
  title: string;
  icon: string;
  levels: number;
};
