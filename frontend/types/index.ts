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
  preferred_language?: string;
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
