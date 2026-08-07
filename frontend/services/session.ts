"use client";

import type { AuthResponse, ChildProfile, User } from "@/types";
import { makeGuestChild } from "@/data/prototype";

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
  sessionStorage.setItem(CHILD_KEY, JSON.stringify(child));
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("little-learning-session"));
  }
}

export function getChild(): ChildProfile | null {
  const raw = sessionStorage.getItem(CHILD_KEY);
  return raw ? (JSON.parse(raw) as ChildProfile) : null;
}

export function getOrCreateGuestChild(): ChildProfile {
  const stored = getChild();
  if (stored) return stored;
  const child = makeGuestChild();
  sessionStorage.setItem(GUEST_KEY, "true");
  saveChild(child);
  return child;
}

export function isGuestSession(): boolean {
  return sessionStorage.getItem(GUEST_KEY) === "true" || !getUser();
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(CHILD_KEY);
  sessionStorage.removeItem(GUEST_KEY);
}
