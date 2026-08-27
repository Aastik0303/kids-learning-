import { apiClient } from "@/services/api/client";
import type { ConductorDirective, ConductorInputPayload } from "@/types/domain";

/**
 * /conductor — see `backend/app/api/conductor.py`.
 *
 * The class is run on the server. There are only four calls, and one of them
 * takes every kind of child input there is: a tap, a spoken answer, a traced
 * letter, silence, a raised hand. One directive comes back each time, and the
 * app renders it.
 *
 * Note what is *not* here: no "next", no "start topic", no "check answer".
 * Those were decisions, and decisions are not the client's to make any more.
 */
export const conductorApi = {
  /** Start or resume today's class. The child chooses nothing to get here. */
  open(childId: string) {
    return apiClient.post<ConductorDirective>(`/conductor/${childId}/open`, {});
  },

  /** Report what the child just did. Reports; does not interpret. */
  send(sessionId: string, payload: ConductorInputPayload) {
    return apiClient.post<ConductorDirective>(`/conductor/sessions/${sessionId}/input`, {
      kind: payload.kind,
      answer: payload.answer ?? "",
      latency_ms: Math.max(0, Math.round(payload.latency_ms ?? 0)),
      confidence: payload.confidence ?? 0.9,
      alternatives: payload.alternatives ?? [],
    });
  },

  /** The same directive again, with nothing moved. Safe after a reload. */
  read(sessionId: string) {
    return apiClient.get<ConductorDirective>(`/conductor/sessions/${sessionId}`);
  },

  pause(sessionId: string) {
    return apiClient.post<ConductorDirective>(`/conductor/sessions/${sessionId}/pause`, {});
  },
};
