import { create } from "zustand";

import { authApi } from "@/services/api/authApi";
import { ApiError } from "@/services/api/client";
import { kv } from "@/services/storage/kv";
import { secureStore } from "@/services/storage/secureStore";
import { track } from "@/services/analytics/analytics";
import type { User } from "@/types/domain";

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
  login: (email: string, password: string) => Promise<boolean>;
  register: (name: string, email: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  continueAsGuest: () => void;
  setPendingIntent: (intent: PendingIntent | null) => void;
  consumePendingIntent: () => PendingIntent | null;
  clearError: () => void;
};

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
      // Token no longer valid server-side (prototype state resets often).
      await secureStore.clearSessionToken();
      set({ status: "guest", pendingIntent: intent });
    } catch {
      // Offline at launch: keep the token and let the child in rather than
      // forcing a sign-in they cannot complete.
      set({ status: "authenticated", sessionToken: token, pendingIntent: intent });
    }
  },

  async login(email, password) {
    set({ isSubmitting: true, error: null });
    try {
      const result = await authApi.login(email, password);
      await secureStore.saveSessionToken(result.session_token);
      set({
        status: "authenticated",
        user: result.user,
        sessionToken: result.session_token,
        isSubmitting: false,
      });
      track("auth_completed", { method: "login" });
      return true;
    } catch (error) {
      set({
        isSubmitting: false,
        error:
          error instanceof ApiError
            ? error.message
            : "We could not sign you in. Please try again.",
      });
      return false;
    }
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
