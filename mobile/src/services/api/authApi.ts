import { apiClient } from "@/services/api/client";
import type { AuthResponse, SessionResponse } from "@/types/domain";

/** POST /auth/* — see `backend/app/api/auth.py`. */
export const authApi = {
  register(name: string, email: string, password: string) {
    return apiClient.post<AuthResponse>("/auth/register", { name, email, password });
  },

  login(email: string, password: string) {
    return apiClient.post<AuthResponse>("/auth/login", { email, password });
  },

  logout(sessionToken: string) {
    return apiClient.post<{ ok: boolean }>("/auth/logout", { session_token: sessionToken });
  },

  /** Validates a stored token on cold start. */
  session(sessionToken: string) {
    return apiClient.get<SessionResponse>("/auth/session", { sessionToken });
  },
};
