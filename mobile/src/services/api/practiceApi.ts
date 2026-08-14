import { apiClient } from "@/services/api/client";
import type {
  PracticeAnswerResponse,
  PracticeStartResponse,
  PracticeTopic,
} from "@/types/domain";

/** /practice — see `backend/app/api/practice.py`. */
export const practiceApi = {
  /** Only topics the child has actually been introduced to come back unlocked. */
  topics(childId: string) {
    return apiClient.get<PracticeTopic[]>(`/practice/topics/${childId}`);
  },

  start(childId: string, topic: string) {
    return apiClient.post<PracticeStartResponse>("/practice/start", {
      child_id: childId,
      topic,
    });
  },

  answer(practiceSessionId: string, activityId: string, answer: string) {
    return apiClient.post<PracticeAnswerResponse>("/practice/answer", {
      practice_session_id: practiceSessionId,
      activity_id: activityId,
      answer,
    });
  },
};
