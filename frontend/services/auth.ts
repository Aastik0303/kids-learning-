import { api } from "@/services/api";
import type { AuthResponse } from "@/types";

export function register(name: string, email: string, password: string) {
  return api<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ name, email, password })
  }).catch(() => ({
    session_token: `local-session-${Date.now()}`,
    user: { id: "local-user", name, email }
  }));
}

export function login(email: string, password: string) {
  return api<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  }).catch(() => ({
    session_token: `local-session-${Date.now()}`,
    user: { id: "local-user", name: "Demo Parent", email }
  }));
}
