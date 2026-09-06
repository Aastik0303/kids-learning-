export type User = {
  id: string;
  name: string;
  email: string;
};

/**
 * A signed-in parent, and the bearer token that says so.
 *
 * `session_token` and `access_token` are the same signed JWT. The first name is
 * what every client already stores and sends back as `X-Demo-Session`; the
 * second, with `token_type` and `expires_in`, is the ordinary bearer shape the
 * API also accepts as `Authorization: Bearer <token>`.
 */
export type AuthResponse = {
  session_token: string;
  access_token: string;
  token_type: string;
  /** Seconds, matching the server-side session the token names. */
  expires_in: number;
  user: User;
};

/** Presentation rules for an age band. Served from the manifest, never hardcoded. */
export type ExperienceMode = {
  mode_id: string;
  applies_to: string[];
  touch_target_px: number;
  max_choices_per_screen: number;
  text_density: "none" | "short_words" | string;
  voice: string;
  idle_thresholds_seconds: number[];
};

export type Topic = {
  topic_id: string;
  subject_id: string;
  class_id: string;
  title: string;
  icon: string;
  sort_order: number;
  subtopics: string[];
  /**
   * One emoji per subtopic, in the same order. Optional, and not only because a
   * topic may author none: a server older than this field omits it entirely, so
   * a caller that assumes an array here crashes against a backend mid-deploy.
   */
  subtopic_icons?: string[];
  /**
   * One plain-language line per subtopic, in the same order — what that point
   * actually means to a child. Optional for the same two reasons as the icons.
   */
  subtopic_easy?: string[];
  /** The whole topic in one friendly line. `objective` stays the grown-up summary. */
  easy_line?: string | null;
  activity_count: number;
  available: boolean;
  passing_score: number;
  star_reward: number;
  objective?: string | null;
  intro_message?: string | null;
  /** "digital" | "hybrid" | "parent_guided" */
  delivery: string;
};

export type Subject = {
  subject_id: string;
  class_id: string;
  title: string;
  /** The child-facing name, when the manifest gives one. Falls back to `title`. */
  fun_name?: string | null;
  icon: string;
  accent: string;
  /** An exact colour for a subject that pins one. Falls back to `accent`. */
  colour?: string | null;
  note?: string | null;
  /** What the subject is, in a line a child can follow. `note` is for grown-ups. */
  easy_line?: string | null;
  sort_order: number;
  topic_count: number;
  subtopic_count: number;
  activity_count: number;
  available: boolean;
  topics: Topic[];
};

export type ClassSummary = {
  class_id: string;
  code: string;
  title: string;
  subtitle?: string | null;
  min_age: number;
  max_age: number;
  experience_mode: string;
  sort_order: number;
  pedagogy?: string | null;
  subject_count: number;
  topic_count: number;
  subtopic_count: number;
  activity_count: number;
};

export type ClassDetail = ClassSummary & {
  experience: ExperienceMode;
  removed_subjects: string[];
  subjects: Subject[];
};

export type SubjectProgress = {
  completed_topics: string[];
  unlocked_topics: string[];
  current_topic_id: string | null;
  scores: Record<string, number>;
};

export type ChildProfile = {
  child_id: string;
  user_id: string;
  name: string;
  birth_year: number;
  birth_month: number;
  age_years: number;
  class_id: string;
  default_class_id: string;
  class_override: string | null;
  experience_mode: string;
  preferred_language: string;
  stars: number;
  current_subject_id: string | null;
  current_topic_id: string | null;
  completed_subjects: string[];
  subject_progress: Record<string, SubjectProgress>;
  weak_skills: string[];
  rewards: string[];
  certificate_unlocked: boolean;
};

/** One item in today's plan. The server decides the order; the client renders it. */
export type PlanItem = {
  topic_id: string;
  /** "<subject>:<topic>" — the id the attempt log and the mastery roll-up use. */
  skill_id: string;
  title: string;
  /** Why the planner put it in today: "new", "revisit" or "prerequisite". */
  reason: string;
  done: boolean;
  current: boolean;
};

/**
 * Today's frozen plan. Written once per child per day, so a refresh, a
 * back-navigation and a second tab all show the same three things.
 */
/**
 * A retention check-in the schedule says is due: something taught two days ago,
 * to be asked again with a different question before today's first stage.
 *
 * It is not a curriculum item and it is deliberately not shaped like one — no
 * `reason`, no `done`, no `current`. Answering it unlocks nothing, pays no star
 * and does not move the day. Adventure shows it so a grown-up can see what the
 * class is about to check, and nothing about it is tappable.
 */
export type RetentionTestItem = {
  test_id: string;
  /** "<subject>:<topic>" — the concept being checked. */
  concept_id: string;
  topic_id: string;
  title: string;
  due_at: string;
};

export type TodayPlan = {
  child_id: string;
  plan_date: string;
  /** "planner_agent" when the LangGraph planner ordered the day, else "deterministic". */
  source: string;
  items: PlanItem[];
  current_topic_id: string | null;
  completed: number;
  total: number;
  /** Every item done. What comes next is tomorrow's plan, not the next level. */
  complete: boolean;
  /** Play Group and Nursery: the app opens today's lesson itself. */
  autopilot: boolean;
  /**
   * The check-ins today's sitting opens with. Part of the schedule and not part
   * of `items`: a check-in is not a level, so nothing that counts or walks the
   * day's levels may pick these up by accident.
   */
  retention_tests?: RetentionTestItem[];
};

/**
 * One level's revision notes: the author's own teaching lines, for going back
 * over something already learned.
 *
 * Every line came out of the syllabus a person wrote — no model is upstream of
 * any of it — so the same level reads the same on every afternoon. `lines` is
 * both what is shown and what is read aloud; `speech` is those lines joined,
 * ready for the narrator. Nothing about opening these marks, scores or unlocks
 * anything, and none of it starts a lesson.
 */
export type TopicNotes = {
  topic_id: string;
  title: string;
  lines: string[];
  /** Asset tokens to draw — the everyday things the author named beside this level. */
  example_items: string[];
  /** The concept's own picture, named by the server; the client owns the SVG. */
  visual_kind: string;
  visual_value: string;
  speech: string;
  /** False when the author has not written anything to revise from yet. */
  has_notes: boolean;
};

/** How an activity is answered. Decided by the server's evaluator registry. */
export type AnswerKind = "choice" | "spoken" | "presentational";

export type Activity = {
  activity_id: string;
  type: string;
  prompt: string;
  visual_items: string[];
  options: string[];
  correct_answer: string | null;
  hint: string;
  difficulty: string;
  answer_kind: AnswerKind;
  skill_id?: string | null;
  accept?: string[];
  min_similarity?: number | null;
  open_ended?: boolean;
  /** Trace activities: what to draw, and how close counts as done. */
  trace_target?: string | null;
  min_accuracy?: number | null;
  /** Shown to the grown-up for a physical-world activity. */
  parent_note?: string | null;
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
  | "TOPIC_OPENED"
  | "TOPIC_STARTED"
  | "TOPIC_QUESTION_LOADED"
  | "TOPIC_ANSWER_CORRECT"
  | "TOPIC_ANSWER_INCORRECT"
  | "TOPIC_COMPLETED"
  | "SUBJECT_COMPLETED"
  | "TOPIC_UNLOCKED"
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
  learning_objective?: string | null;
  prompt: string;
  answer_type?: string | null;
  options: string[];
  correct_answer?: string | null;
  child_answer?: string | null;
  attempt: number;
  hint?: string | null;
  visual_items?: string[];
  accepted_answers?: string[];
  recent_answers?: string[];
  example?: string | null;
  difficulty?: string | null;
};

export type GuideRequest = {
  session_id?: string | null;
  child_id?: string | null;
  mode: GuideMode;
  event: GuideEvent;
  route: string;
  screen: string;
  feature: string;
  class_id?: string | null;
  experience_mode?: string;
  preferred_language?: string;
  /** The child's own clock hour (0-23), so greetings match their morning. */
  local_hour?: number;
  conversation?: Array<{
    role: "user" | "assistant";
    content: string;
  }>;
  question?: GuideQuestionContext | null;
  progress?: {
    current_class?: string | null;
    current_subject?: string | null;
    current_topic?: string | null;
    last_completed_topic?: string | null;
    last_completed_title?: string | null;
    weak_skills?: string[];
    session_stars?: number;
  } | null;
  allowed_visual_targets?: string[];
  available_actions: GuideActionType[];
  available_targets: string[];
};

export type GuideResponse = {
  message: string;
  strategy: "welcome" | "navigation" | "read_question" | "visual_explanation" | "hint" | "re_explain" | "celebrate" | "help" | "none";
  avatar: import("@/components/avatar/avatar.types").AvatarPayload;
  ui_action: {
    type: GuideActionType;
    target: string | null;
  };
  visual_action: {
    type: "none" | "pulse" | "highlight" | "highlight_sequence" | "dim_others" | "group_objects" | "trace_shape" | "show_example";
    targets: string[];
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
    subject_id?: string | null;
    topic_id?: string | null;
    target_id?: string | null;
    route?: string;
    label?: string;
  };
};
