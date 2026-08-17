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
