/**
 * The AI Teacher's wire types, and the schedule's.
 *
 * These mirror `frontend/types/index.ts` and `frontend/services/aiTeacher.ts`
 * field for field, because both clients read the same endpoints: the web app
 * and this one are the same class, not two products that happen to share a
 * backend. A field renamed on the server has to move in both places, and a
 * field this client does not understand is simply not read - never guessed at.
 */

/**
 * One turn of the class.
 *
 * The client renders it and reports what the child did. It decides nothing:
 * not whether an answer was right, not what comes next, not when the day ends.
 * `stage.judge` marks in pure Python on the server from the author's own key,
 * which matters more now than it ever did, because the verdict pays stars.
 */
export type TeacherTurn = {
  session_id: string;
  child_id: string;
  /** Which item of today's frozen plan this is, and how many the day holds. */
  stage: number;
  stages_total?: number;
  /** How many of the stage's five questions have settled. Progress, never a score. */
  questions_asked: number;
  questions_per_stage: number;
  topic_id: string;
  topic_title: string;
  speech: string;
  question: string;
  strategy: string;
  source: string;
  retrieval: string;
  /** "explain" / "say_it" / "draw" / "match" / "quiz" / "retention" / "poem". */
  step?: string;
  /** What to collect: "ready", "voice", "trace", "tap" or "done". */
  expects?: string;
  step_index?: number;
  steps_total?: number;
  /** 1 asks, 2 hints, 3 reveals. A reveal is told, not tested, and never marked. */
  attempt?: number;
  attempts_allowed?: number;
  is_hint?: boolean;
  is_reveal?: boolean;
  /** A check-in on something taught two days ago. Marked into nothing. */
  is_retention_test?: boolean;
  retention_test_id?: string;
  retention_remaining?: number;
  trace_target?: string;
  /** What the child may tap. Which one is right is never sent. */
  options?: string[];
  /** The picture, named by the server; the client owns the artwork. */
  visual_kind?: string;
  visual_value?: string;
  example_items?: string[];
  /** Everyday words belonging to this concept's siblings - never illustrated here. */
  not_examples?: string[];
  is_poem?: boolean;
  feedback?: string;
  /** Null when the turn was not an answer - the reveal included. */
  is_correct?: boolean | null;
  advanced?: boolean;
  day_complete?: boolean;
  topic_completed?: boolean;
  next_topic_unlocked?: boolean;
  stars_earned?: number;
};

/** One level of today's frozen plan. */
export type PlanItem = {
  topic_id: string;
  /** "<subject>:<topic>" - the id the attempt log and the mastery roll-up use. */
  skill_id: string;
  title: string;
  /** Why the planner put it in today: "new", "revisit" or "prerequisite". */
  reason: string;
  done: boolean;
  current: boolean;
};

/**
 * A retention check-in the scheduler says is due.
 *
 * Deliberately not shaped like a plan item: no `done`, no `current`, no
 * `reason`. Answering one unlocks nothing, pays no star and does not move the
 * day. It is shown so a grown-up can see what the class is about to check.
 */
export type RetentionTestItem = {
  test_id: string;
  concept_id: string;
  topic_id: string;
  title: string;
  due_at: string;
};

/** Today's frozen plan: written once per child per day. */
export type TodayPlan = {
  child_id: string;
  plan_date: string;
  source: string;
  items: PlanItem[];
  current_topic_id: string | null;
  completed: number;
  total: number;
  complete: boolean;
  autopilot: boolean;
  retention_tests?: RetentionTestItem[];
};

/** One level of the syllabus, as the Adventure map shows it. */
export type CurriculumTopic = {
  topic_id: string;
  subject_id: string;
  class_id: string;
  title: string;
  icon: string;
  sort_order: number;
  subtopics: string[];
  subtopic_icons?: string[];
  subtopic_easy?: string[];
  easy_line?: string | null;
  activity_count: number;
  available: boolean;
  passing_score: number;
  star_reward: number;
  objective?: string | null;
  intro_message?: string | null;
  delivery: string;
};

export type CurriculumSubject = {
  subject_id: string;
  class_id: string;
  title: string;
  fun_name?: string | null;
  icon: string;
  accent: string;
  colour?: string | null;
  note?: string | null;
  easy_line?: string | null;
  sort_order: number;
  topic_count: number;
  subtopic_count: number;
  activity_count: number;
  available: boolean;
  topics: CurriculumTopic[];
};

export type ClassSummaryInfo = {
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

export type ClassDetail = ClassSummaryInfo & {
  removed_subjects: string[];
  subjects: CurriculumSubject[];
};

/**
 * One thing a child can tap in a level's game.
 *
 * `token` is the asset name the author wrote - the client turns it into a
 * picture and draws nothing at all for one it has no artwork for.
 */
export type GameOption = {
  token: string;
  label: string;
};

/**
 * One asking in a game. `answer` is an index into `options` and never a word,
 * because the server picked it with the same rule the class marks a tap with.
 */
export type GameRound = {
  ask: string;
  say: string;
  options: GameOption[];
  answer: number;
};

export type LevelGame = {
  topic_id: string;
  game_id: string;
  kind: "find" | "pairs" | "pop" | string;
  title: string;
  blurb: string;
  icon: string;
  rounds: GameRound[];
  /** The matching game's pack: one token per pair, dealt twice by the client. */
  tokens: string[];
};

export type TopicGames = {
  topic_id: string;
  title: string;
  games: LevelGame[];
};
