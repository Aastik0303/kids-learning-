import { api } from "@/services/api";

export type TeacherTurn = {
  session_id: string;
  child_id: string;
  /**
   * Which item of today's frozen plan this is, and how many the day holds.
   * A stage is a level out of the schedule, so these two numbers *are* the
   * schedule as the child sees it.
   */
  stage: number;
  stages_total?: number;
  /**
   * How many of the stage's five questions have been settled, and how many
   * there are. This is progress, not a score — there is no score any more, and
   * nothing on this screen may draw a number that goes down when a child is
   * wrong. A question that had to be answered *for* the child counts here the
   * same as one they got.
   */
  questions_asked: number;
  questions_per_stage: number;
  topic_id: string;
  topic_title: string;
  speech: string;
  question: string;
  /** Which of the nine teaching strategies this turn used. */
  strategy: string;
  /** "llm" when the big model wrote it, "template" when the notes did. */
  source: string;
  /** "embeddings" or "keyword" — which retriever answered. */
  retrieval: string;
  /**
   * Where in the lesson this turn is — "explain" / "say_it" / "draw" / "match"
   * / "quiz" — and what to collect for it: "ready", "voice", "trace" or "tap".
   * The client renders the step; it never chooses one.
   */
  step?: string;
  expects?: string;
  step_index?: number;
  steps_total?: number;
  /**
   * Which of the question's three turns this is. 1 asks it; 2 asks the same one
   * again with `is_hint`, a deeper explanation and the choices to pick from;
   * 3 is `is_reveal` — the answer told and explained, expecting nothing back
   * but "ready". A reveal is never marked, because it was not a test.
   */
  attempt?: number;
  attempts_allowed?: number;
  is_hint?: boolean;
  is_reveal?: boolean;
  /** What to trace, on the drawing step. */
  trace_target?: string;
  /**
   * What the child may tap. Empty when the question wants a spoken answer.
   * Which one is right is not said here — the server marks the answer.
   */
  options?: string[];
  /**
   * The picture to draw beside the explanation, named by the server rather than
   * drawn by it: "letter" / "number" / "count" / "shape" / "colour", and the
   * value. Empty when this turn has no picture. No markup ever crosses this.
   */
  visual_kind?: string;
  visual_value?: string;
  feedback?: string;
  /** Null when the turn was not an answer — the reveal included. */
  is_correct?: boolean | null;
  advanced?: boolean;
  /**
   * Every stage of today's plan is through. There is nothing to answer and
   * nothing to open — `expects` is "done" — and the next lesson is tomorrow's.
   * The lock is the server's; the client only says so.
   */
  day_complete?: boolean;
  /** The level this stage just finished passed, and what that opened. */
  topic_completed?: boolean;
  next_topic_unlocked?: boolean;
  stars_earned?: number;
};

/**
 * /playground/teacher — the AI Teacher, which is the class.
 *
 * A retrieval-grounded agent that teaches from the project's own notes and asks
 * its own questions, run straight off today's frozen plan: one stage per planned
 * item, in order, and when the last one is through the day is shut until
 * tomorrow. Finishing a stage marks the level done and unlocks the next one on
 * the Adventure map.
 *
 * A stage is five questions. Each one is asked, then asked again with a hint if
 * it did not land, and then answered and explained if it still did not — so
 * nobody is drilled and nobody is left stuck.
 *
 * Whether an answer was right is decided on the server in plain Python, never by
 * the model that asked the question — which matters more now that the verdict
 * pays stars. The path still says `playground` because that is where this
 * started; nothing about it is a sandbox any more.
 */
export function openTeacher(childId: string) {
  return api<TeacherTurn>(`/playground/teacher/${childId}/open`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function answerTeacher(sessionId: string, answer: string) {
  return api<TeacherTurn>(`/playground/teacher/sessions/${sessionId}/answer`, {
    method: "POST",
    body: JSON.stringify({ answer })
  });
}

/**
 * Something the child asked of their own accord.
 *
 * Not an answer: the lesson does not move, nothing is marked, and the question
 * the bot had already asked is still waiting when the answer is done.
 */
export function askTeacher(sessionId: string, question: string) {
  return api<TeacherTurn>(`/playground/teacher/sessions/${sessionId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question })
  });
}
