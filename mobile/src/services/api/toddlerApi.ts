import { apiClient } from "@/services/api/client";
import type {
  LearningMode,
  ToddlerLevel,
  ToddlerModule,
  ToddlerModuleSummary,
  ToddlerResponse,
} from "@/types/domain";

/** /toddler — the voice-first, one-activity-at-a-time surface for ages 1–3. */
export const toddlerApi = {
  /**
   * The backend owns the age→mode rule (under 3 ⇒ toddler). Asking it
   * rather than hardcoding keeps the threshold in one place.
   */
  resolveMode(age: number) {
    return apiClient.post<{ age: number; learning_mode: LearningMode }>("/toddler/mode", { age });
  },

  modules() {
    return apiClient.get<ToddlerModuleSummary[]>("/toddler/modules");
  },

  curriculum(module: ToddlerModule) {
    return apiClient.get<ToddlerLevel[]>(`/toddler/curriculum/${module}`);
  },

  start(childId: string, module: ToddlerModule, level = 1, practice = false) {
    return apiClient.post<ToddlerResponse>("/toddler/start", {
      child_id: childId,
      module,
      level,
      practice,
    });
  },

  answer(sessionId: string, answer: string, recognizedSpeech = answer) {
    return apiClient.post<ToddlerResponse>("/toddler/answer", {
      session_id: sessionId,
      answer,
      recognized_speech: recognizedSpeech,
    });
  },
};
