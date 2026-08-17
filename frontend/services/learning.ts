import { api } from "@/services/api";
import type { LearningResponse } from "@/types";

/**
 * A lesson is one topic. Correctness, score and unlocking are decided by the
 * server, so there is no local scoring path here to drift out of step with it.
 */
export function startLearning(child_id: string, topic_id: string) {
  return api<LearningResponse>("/learning/start", {
    method: "POST",
    body: JSON.stringify({ child_id, topic_id })
  });
}

export function answerLearning(session_id: string, answer: string) {
  return api<LearningResponse>("/learning/answer", {
    method: "POST",
    body: JSON.stringify({ session_id, answer })
  });
}

export function continueLearning(session_id: string) {
  return api<LearningResponse>(`/learning/continue/${session_id}`, { method: "POST" });
}

export function getLearningSession(session_id: string) {
  return api<LearningResponse>(`/learning/session/${session_id}`);
}
