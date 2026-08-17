"use client";

import type { AuthResponse, ChildProfile, User } from "@/types";

const TOKEN_KEY = "demo_session_token";
const USER_KEY = "demo_user";
const CHILD_KEY = "demo_child";
const GUEST_KEY = "demo_guest_active";

export function saveAuth(auth: AuthResponse) {
  sessionStorage.setItem(TOKEN_KEY, auth.session_token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(auth.user));
  sessionStorage.removeItem(GUEST_KEY);
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getUser(): User | null {
  const raw = sessionStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}

export function saveChild(child: ChildProfile) {
  const next = JSON.stringify(child);
  // Only announce a profile that actually changed. Listeners re-read the child
  // from the server, which saves it again; announcing an identical write would
  // make that loop forever instead of settling once the two agree.
  if (sessionStorage.getItem(CHILD_KEY) === next) return;
  sessionStorage.setItem(CHILD_KEY, next);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("little-learning-session"));
  }
}

export function getChild(): ChildProfile | null {
  const raw = sessionStorage.getItem(CHILD_KEY);
  return raw ? (JSON.parse(raw) as ChildProfile) : null;
}

export function isGuestSession(): boolean {
  return sessionStorage.getItem(GUEST_KEY) === "true" || !getUser();
}

export function markGuestSession() {
  sessionStorage.setItem(GUEST_KEY, "true");
}

/**
 * Drop the stored child while leaving the parent signed in.
 *
 * Used when the server no longer recognises the child: profiles live in memory
 * in this prototype, so a server restart leaves the browser holding an id that
 * no longer exists. Keeping it would dead-end every child screen.
 */
export function forgetChild() {
  sessionStorage.removeItem(CHILD_KEY);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("little-learning-session"));
  }
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(CHILD_KEY);
  sessionStorage.removeItem(GUEST_KEY);
}
