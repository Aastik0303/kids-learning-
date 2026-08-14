import { apiClient } from "@/services/api/client";
import type { LearningResponse, PathSummary, Stage } from "@/types/domain";

/** /learning — see `backend/app/api/learning.py`. */
export const learningApi = {
  /** The four core paths plus the mixed final. */
  listPaths() {
    return apiClient.get<PathSummary[]>("/learning/paths");
  },

  listStages(pathId: string) {
    return apiClient.get<Stage[]>(`/learning/paths/${pathId}/stages`);
  },

  start(childId: string, pathId: string, stageNumber: number) {
    return apiClient.post<LearningResponse>("/learning/start", {
      child_id: childId,
      path_id: pathId,
      stage_number: stageNumber,
    });
  },

  /**
   * Submits an answer. Correctness, score, stars and unlocking are all
   * decided here on the server — the app only renders the verdict.
   */
  answer(sessionId: string, answer: string) {
    return apiClient.post<LearningResponse>("/learning/answer", {
      session_id: sessionId,
      answer,
    });
  },

  /** Re-serves the current question after a wrong answer. */
  retry(sessionId: string) {
    return apiClient.post<LearningResponse>(`/learning/retry/${sessionId}`);
  },

  /** Advances to the next activity in the stage. */
  continue(sessionId: string) {
    return apiClient.post<LearningResponse>(`/learning/continue/${sessionId}`);
  },

  /** Used to restore a lesson after the app was backgrounded. */
  getSession(sessionId: string) {
    return apiClient.get<LearningResponse>(`/learning/session/${sessionId}`);
  },
};
