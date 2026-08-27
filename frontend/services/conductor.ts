import { api } from "@/services/api";
import type { ConductorDirective, ConductorInputPayload } from "@/types";

/**
 * /conductor — see `backend/app/api/conductor.py`.
 *
 * The class is run on the server. Four calls, and one of them takes every kind
 * of child input there is: a tap, a spoken answer, a traced letter, silence, a
 * raised hand. One directive comes back each time and the app renders it.
 *
 * Note what is *not* here: no "next", no "start topic", no "check answer".
 * Those were decisions, and decisions are not the client's to make.
 */

/**
 * Start or resume today's class. The child chooses nothing to get here.
 *
 * `topicId` is only ever sent from the Adventure map, where a grown-up has
 * picked a level to sit through. It names which topic to conduct and nothing
 * else: the day's frozen plan still decides whether it may be opened, and an
 * off-plan level comes back as `NOT_TODAYS_PLAN`.
 */
export function openClass(childId: string, topicId?: string | null) {
  return api<ConductorDirective>(`/conductor/${childId}/open`, {
    method: "POST",
    body: JSON.stringify(topicId ? { topic_id: topicId } : {})
  });
}

/** Report what the child just did. Reports; does not interpret. */
export function sendClassInput(sessionId: string, payload: ConductorInputPayload) {
  return api<ConductorDirective>(`/conductor/sessions/${sessionId}/input`, {
    method: "POST",
    body: JSON.stringify({
      kind: payload.kind,
      answer: payload.answer ?? "",
      latency_ms: Math.max(0, Math.round(payload.latency_ms ?? 0)),
      confidence: payload.confidence ?? 0.9,
      alternatives: payload.alternatives ?? []
    })
  });
}
