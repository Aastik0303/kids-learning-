import { api } from "@/services/api";
import type { AuthResponse, GoogleAuthConfig, LoginResult } from "@/types";

/**
 * No offline fallback here on purpose.
 *
 * These used to mint a `local-session-…` token when the request failed, which
 * made a down backend look like a successful login: the header said "Parent",
 * but every later call carried a token the server had never issued, so each
 * screen failed separately and none of them said why. Letting the error through
 * gives the parent one honest message instead.
 */
export function register(name: string, email: string, password: string) {
  return api<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ name, email, password })
  });
}

/**
 * Check the password. This does **not** necessarily sign anybody in.
 *
 * Where the emailed code is switched on, the answer is a challenge with no
 * token in it, and `verifyCode` is what finishes the sign-in. Callers must read
 * which of the two came back - `isSignInChallenge` - rather than reaching for
 * `session_token` and getting undefined.
 */
export function login(email: string, password: string) {
  return api<LoginResult>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

/** Spend the emailed code. This is what mints the session on the password path. */
export function verifyCode(challenge_id: string, code: string) {
  return api<AuthResponse>("/auth/otp/verify", {
    method: "POST",
    body: JSON.stringify({ challenge_id, code })
  });
}

/** Another code on the same challenge. Behind a cooldown on the server. */
export function resendCode(challenge_id: string) {
  return api<{ ok: boolean; message: string; resend_after: number; dev_code: string | null }>(
    "/auth/otp/resend",
    { method: "POST", body: JSON.stringify({ challenge_id }) }
  );
}

/**
 * Whether to draw Google's button, and with which client id.
 *
 * The client id comes from the server rather than from this app's own
 * environment, so there is one configured value instead of two that can drift
 * apart - and the button cannot appear on a deployment whose server has no way
 * to verify what Google hands back.
 */
export function googleConfig() {
  return api<GoogleAuthConfig>("/auth/google/config").catch(
    (): GoogleAuthConfig => ({ enabled: false, client_id: "" })
  );
}

/**
 * Finish a Google sign-in.
 *
 * `credential` is the ID token Google's own script produced. It is only an
 * identity once the server has checked its signature against Google's keys and
 * its audience against this app's client id, so nothing here reads it - not the
 * email, not the name. What comes back is the app's ordinary session.
 */
export function signInWithGoogle(credential: string) {
  return api<AuthResponse>("/auth/google", {
    method: "POST",
    body: JSON.stringify({ credential })
  });
}

/**
 * End the session on the server too.
 *
 * "Logout" used to clear `sessionStorage` and reload, which left the row in
 * `auth_sessions` alive and valid - a token that had supposedly been signed out
 * still worked. The local clear stays (it is what the UI reads), and the server
 * is told as well; a failure is swallowed, because a parent who pressed logout
 * must end up signed out of this browser either way.
 */
export function logout(session_token: string) {
  return api<{ ok: boolean }>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ session_token })
  }).catch(() => ({ ok: false }));
}

/**
 * Start a password reset.
 *
 * The answer is deliberately the same whether or not the address is
 * registered, so this can never be used to find out who has an account.
 * `reset_token` is filled in outside production only, where there is no mailer
 * to send the link; in production it is always null and the page says to check
 * the inbox.
 */
export function forgotPassword(email: string) {
  return api<{ ok: boolean; message: string; reset_token: string | null }>("/auth/password/forgot", {
    method: "POST",
    body: JSON.stringify({ email })
  });
}

/** Spend a reset token and set a new password. Every device is signed out. */
export function resetPassword(token: string, password: string) {
  return api<{ ok: boolean; message: string }>("/auth/password/reset", {
    method: "POST",
    body: JSON.stringify({ token, password })
  });
}
