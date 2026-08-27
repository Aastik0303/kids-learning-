import { api } from "@/services/api";

export type ActivityAttempt = {
  id: string;
  child_id: string;
  session_id: string;
  activity_id: string;
  topic: string;
  skill: string;
  level_id: string | null;
  child_answer: string;
  is_correct: boolean;
  attempt_number: number;
  created_at: string;
};

export type PlanHistoryEntry = {
  plan_date: string;
  source: string;
  items: { topic_id: string; skill_id: string; title: string; reason: string; done: boolean }[];
};

/**
 * The attempt log — `/history` — as the parent surface reads it.
 *
 * Every answer a child gives is written here by `history_service`, and until
 * now nothing in the web app ever read it back: the parent's progress screen
 * showed stars and a list of topic ids and nothing about what actually
 * happened. It is a read of the same rows the branch engine reasons over, so a
 * parent and the app are looking at one record, not two.
 */
export function getHistory(childId: string) {
  return api<{ child_id: string; attempts?: ActivityAttempt[] }>(`/history/${childId}`);
}

/** The days the planner has already frozen. */
export function getPlanHistory(childId: string, days = 7) {
  return api<{ child_id: string; plans?: PlanHistoryEntry[] }>(
    `/plans/${childId}/history?days=${days}`
  );
}
