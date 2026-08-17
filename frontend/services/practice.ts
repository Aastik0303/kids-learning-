import { api } from "@/services/api";
import type { Activity } from "@/types";
import type { AvatarPayload } from "@/components/avatar/avatar.types";

export type PracticeSubject = {
  subject_id: string;
  title: string;
  class_id: string;
  icon: string;
  unlocked: boolean;
  has_activities: boolean;
  topic_count: number;
  /** The child-facing name, the pinned colour and the plain-words line, when the
      manifest gives them. All optional: an older server omits them entirely. */
  fun_name?: string | null;
  colour?: string | null;
  easy_line?: string | null;
  /** The topics this practice draws from, named rather than counted. */
  topic_titles?: string[];
};

export type PracticeSession = {
  practice_session_id: string;
  subject_id: string;
  subject_title: string;
  subject_fun_name?: string | null;
  subject_easy_line?: string | null;
  activities: Activity[];
  selection_reason: string;
};

export type PracticeAnswerResult = {
  is_correct: boolean;
  feedback: string;
  hint: string | null;
  attempt_number?: number;
  question_changed?: boolean;
  avatar?: AvatarPayload | null;
};

export function practiceSubjects(childId: string) {
  return api<PracticeSubject[]>(`/practice/subjects/${childId}`);
}

export function startPractice(child_id: string, subject_id: string) {
  return api<PracticeSession>("/practice/start", {
    method: "POST",
    body: JSON.stringify({ child_id, subject_id })
  });
}

export function answerPractice(practice_session_id: string, activity_id: string, answer: string) {
  return api<PracticeAnswerResult>("/practice/answer", {
    method: "POST",
    body: JSON.stringify({ practice_session_id, activity_id, answer })
  });
}
