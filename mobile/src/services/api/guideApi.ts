import { env } from "@/config/env";
import { apiClient } from "@/services/api/client";
import type { GuideRequest, GuideResponse } from "@/types/guide";

/**
 * POST /agent/guide — the single AI-shaped call in the product.
 *
 * The request carries the full safe context (route, screen, visible
 * question, allowed actions and targets); the response is structured JSON
 * that still has to clear `ai/guideSchema.ts` before it can touch the UI.
 */
export const guideApi = {
  ask(payload: GuideRequest, signal?: AbortSignal) {
    // Stamped here rather than at each call site, so every guide event carries
    // the child's real local hour and no greeting can drift to server time.
    const body: GuideRequest = { local_hour: new Date().getHours(), ...payload };
    return apiClient.post<GuideResponse>("/agent/guide", body, {
      timeoutMs: env.guideTimeoutMs,
      // One retry only. A child waiting on the avatar would rather get a
      // static fallback line than sit through three backoffs.
      retries: 1,
      signal,
    });
  },
};
