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
    return apiClient.post<GuideResponse>("/agent/guide", payload, {
      timeoutMs: env.guideTimeoutMs,
      // One retry only. A child waiting on the avatar would rather get a
      // static fallback line than sit through three backoffs.
      retries: 1,
      signal,
    });
  },
};
