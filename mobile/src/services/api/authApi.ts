import { apiClient } from "@/services/api/client";
import type { AuthResponse, LoginResult, SessionResponse } from "@/types/domain";

/**
 * Sign-in and "send it again" wait on an SMTP handshake on the server (its own
 * timeout is ten seconds). The CRUD budget of six gave up on a code that was
 * already on its way to the parent.
 */
const MAIL_TIMEOUT_MS = 15000;

/** POST /auth/* — see `backend/app/api/auth.py`. */
export const authApi = {
  register(name: string, email: string, password: string) {
    return apiClient.post<AuthResponse>("/auth/register", { name, email, password });
  },

  /**
   * Check the password. This does **not** necessarily sign anybody in.
   *
   * Where the emailed code is switched on, what comes back is a challenge with
   * no token in it and `verifyCode` finishes the sign-in. Callers must read
   * which of the two arrived - `isSignInChallenge` - rather than reaching for
   * `session_token` and getting undefined.
   */
  login(email: string, password: string) {
    return apiClient.post<LoginResult>("/auth/login", { email, password }, { timeoutMs: MAIL_TIMEOUT_MS });
  },

  /** Spend the emailed code. The only thing that mints a session on this path. */
  verifyCode(challengeId: string, code: string) {
    return apiClient.post<AuthResponse>("/auth/otp/verify", {
      challenge_id: challengeId,
      code,
    });
  },

  /** Another code on the same challenge. Behind a cooldown on the server. */
  resendCode(challengeId: string) {
    return apiClient.post<{ ok: boolean; message: string; resend_after: number; dev_code: string | null }>(
      "/auth/otp/resend",
      { challenge_id: challengeId },
      { timeoutMs: MAIL_TIMEOUT_MS },
    );
  },

  logout(sessionToken: string) {
    return apiClient.post<{ ok: boolean }>("/auth/logout", { session_token: sessionToken });
  },

  /** Validates a stored token on cold start. */
  session(sessionToken: string) {
    return apiClient.get<SessionResponse>("/auth/session", { sessionToken });
  },
};
