import { create } from "zustand";

import { authApi } from "@/services/api/authApi";
import { ApiError } from "@/services/api/client";
import { kv } from "@/services/storage/kv";
import { secureStore } from "@/services/storage/secureStore";
import { track } from "@/services/analytics/analytics";
import { isSignInChallenge } from "@/types/domain";
import type { AuthResponse, SignInChallenge, User } from "@/types/domain";

/**
 * A destination the child tapped before they were allowed in. Held so the
 * app can drop them exactly there after auth + child setup, instead of
 * dumping them on a generic home screen (spec section 2).
 */
export type PendingIntent = {
  /** Navigator route name to land on. */
  screen: string;
  /** Params for that route, already validated by the caller. */
  params?: Record<string, unknown>;
  /** Human label, so the auth screen can say what they're heading back to. */
  label: string;
};

export type AuthStatus = "unknown" | "guest" | "authenticated";

type AuthState = {
  status: AuthStatus;
  user: User | null;
  sessionToken: string | null;
  pendingIntent: PendingIntent | null;
  isSubmitting: boolean;
  error: string | null;

  restore: () => Promise<void>;
  /**
   * Returns what happened rather than a bare boolean: signing in may now stop
   * at an emailed code, and the caller has to know which.
   */
  login: (email: string, password: string) => Promise<"signed-in" | "code-sent" | "failed">;
  /** The challenge waiting on a code, when `login` answered "code-sent". */
  pendingChallenge: SignInChallenge | null;
  verifyCode: (code: string) => Promise<boolean>;
  resendCode: () => Promise<string | null>;
  clearChallenge: () => void;
  register: (name: string, email: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  continueAsGuest: () => void;
  setPendingIntent: (intent: PendingIntent | null) => void;
  consumePendingIntent: () => PendingIntent | null;
  clearError: () => void;
};


/**
 * Take a session and become signed in. Shared, so the password path and the
 * code path cannot drift into storing different things.
 */
async function adopt(
  set: (partial: Partial<AuthState>) => void,
  result: AuthResponse,
  method: "login" | "register" | "login_otp",
): Promise<void> {
  await secureStore.saveSessionToken(result.session_token);
  set({
    status: "authenticated",
    user: result.user,
    sessionToken: result.session_token,
    isSubmitting: false,
  });
  track("auth_completed", { method });
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: "unknown",
  user: null,
  sessionToken: null,
  pendingIntent: null,
  isSubmitting: false,
  error: null,

  /** Cold-start restore. Validates the stored token before trusting it. */
  async restore() {
    const [token, intent] = await Promise.all([
      secureStore.getSessionToken(),
      kv.get<PendingIntent>("learnkids.pending_intent"),
    ]);

    if (!token) {
      set({ status: "guest", pendingIntent: intent });
      return;
    }

    try {
      const result = await authApi.session(token);
      if (result.user) {
        set({ status: "authenticated", user: result.user, sessionToken: token, pendingIntent: intent });
        return;
      }
      // Token no longer valid server-side: signed out elsewhere, expired, or
      // ended by a password reset.
      await secureStore.clearSessionToken();
      set({ status: "guest", pendingIntent: intent });
    } catch {
      // Offline at launch: keep the token and let the child in rather than
      // forcing a sign-in they cannot complete.
      set({ status: "authenticated", sessionToken: token, pendingIntent: intent });
    }
  },

  pendingChallenge: null,

  async login(email, password) {
    set({ isSubmitting: true, error: null });
    try {
      const result = await authApi.login(email, password);
      if (isSignInChallenge(result)) {
        // The password was right and that is all. There is no session yet and
        // nothing in `result` is one; the code step is what creates it.
        set({ isSubmitting: false, pendingChallenge: result });
        return "code-sent";
      }
      await adopt(set, result, "login");
      return "signed-in";
    } catch (error) {
      set({
        isSubmitting: false,
        error:
          error instanceof ApiError
            ? error.message
            : "We could not sign you in. Please try again.",
      });
      return "failed";
    }
  },

  async verifyCode(code) {
    const challenge = get().pendingChallenge;
    if (!challenge) return false;
    set({ isSubmitting: true, error: null });
    try {
      const result = await authApi.verifyCode(challenge.challenge_id, code);
      await adopt(set, result, "login_otp");
      set({ pendingChallenge: null });
      return true;
    } catch (error) {
      set({
        isSubmitting: false,
        error:
          error instanceof ApiError
            ? error.message
            : "That code did not work. Please try again.",
      });
      return false;
    }
  },

  async resendCode() {
    const challenge = get().pendingChallenge;
    if (!challenge) return null;
    set({ error: null });
    try {
      const again = await authApi.resendCode(challenge.challenge_id);
      set({
        pendingChallenge: { ...challenge, resend_after: again.resend_after, dev_code: again.dev_code },
      });
      return again.message;
    } catch (error) {
      set({
        error:
          error instanceof ApiError ? error.message : "We could not send another code.",
      });
      return null;
    }
  },

  clearChallenge() {
    set({ pendingChallenge: null, error: null });
  },

  async register(name, email, password) {
    set({ isSubmitting: true, error: null });
    try {
      const result = await authApi.register(name, email, password);
      await secureStore.saveSessionToken(result.session_token);
      set({
        status: "authenticated",
        user: result.user,
        sessionToken: result.session_token,
        isSubmitting: false,
      });
      track("auth_completed", { method: "register" });
      return true;
    } catch (error) {
      set({
        isSubmitting: false,
        error:
          error instanceof ApiError
            ? error.message
            : "We could not create that account. Please try again.",
      });
      return false;
    }
  },

  async logout() {
    const token = get().sessionToken;
    if (token) {
      // Fire and forget: a failed server logout must not trap the parent
      // in a signed-in state on the device.
      authApi.logout(token).catch(() => undefined);
    }
    await Promise.all([secureStore.clearSessionToken(), kv.clearSessionScoped()]);
    set({ status: "guest", user: null, sessionToken: null, pendingIntent: null, error: null });
  },

  continueAsGuest() {
    set({ status: "guest" });
  },

  setPendingIntent(intent) {
    set({ pendingIntent: intent });
    if (intent) {
      void kv.set("learnkids.pending_intent", intent);
    } else {
      void kv.remove("learnkids.pending_intent");
    }
  },

  /** Read-and-clear, so a resumed intent never fires twice. */
  consumePendingIntent() {
    const intent = get().pendingIntent;
    if (intent) {
      set({ pendingIntent: null });
      void kv.remove("learnkids.pending_intent");
    }
    return intent;
  },

  clearError() {
    set({ error: null });
  },
}));
