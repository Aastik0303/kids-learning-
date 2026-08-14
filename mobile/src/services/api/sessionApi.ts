import { apiClient, checkHealth } from "@/services/api/client";
import type { ChildProfile } from "@/types/domain";

/**
 * Cross-cutting session concerns that don't belong to a single feature:
 * connectivity probing and the dev-only seed route.
 */
export const sessionApi = {
  health: checkHealth,

  /**
   * Dev-only: unlocks the mixed final path so the certificate flow can be
   * demoed without playing every stage. Guarded server-side in
   * `backend/app/api/dev.py`.
   */
  seedChild(childId: string) {
    return apiClient.post<ChildProfile>(`/dev/seed/${childId}`);
  },
};
