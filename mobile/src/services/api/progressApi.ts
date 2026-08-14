import { apiClient } from "@/services/api/client";
import type {
  CertificateResponse,
  HistoryResponse,
  ProgressResponse,
  RewardsResponse,
} from "@/types/domain";

/** /progress and /history — parent-facing reporting plus reward state. */
export const progressApi = {
  get(childId: string) {
    return apiClient.get<ProgressResponse>(`/progress/${childId}`);
  },

  rewards(childId: string) {
    return apiClient.get<RewardsResponse>(`/progress/${childId}/rewards`);
  },

  /**
   * Certificate eligibility is decided server-side by
   * `certificate_service.py`. The app only renders `unlocked`.
   */
  certificate(childId: string) {
    return apiClient.get<CertificateResponse>(`/progress/${childId}/certificate`);
  },

  history(childId: string) {
    return apiClient.get<HistoryResponse>(`/history/${childId}`);
  },
};
