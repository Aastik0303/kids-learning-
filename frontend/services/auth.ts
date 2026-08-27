import { api } from "@/services/api";
import type { AuthResponse } from "@/types";

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

export function login(email: string, password: string) {
  return api<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
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
 * registered, so this can never be used to find out who has an account. There
 * is no mailer yet, so outside production the server hands the token back in
 * `reset_token` and the page shows it - the honest shape of an unfinished
 * feature, rather than a flow that cannot be completed at all.
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
