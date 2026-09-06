"use client";

import type { AuthResponse, ChildProfile, User } from "@/types";

const TOKEN_KEY = "demo_session_token";
const USER_KEY = "demo_user";
const CHILD_KEY = "demo_child";
const GUEST_KEY = "demo_guest_active";

const KEYS = [TOKEN_KEY, USER_KEY, CHILD_KEY, GUEST_KEY];

/**
 * Where the signed-in parent is remembered.
 *
 * This used to be `sessionStorage`, and that is why a parent had to sign in
 * again every single time. `sessionStorage` is scoped to one browser tab and is
 * emptied the moment that tab is closed - so the server's thirty-day session
 * was never the thing that expired. The token was still valid, the
 * `auth_sessions` row was still open, and the browser had simply thrown its
 * copy away between one visit and the next.
 *
 * So the parent's session lives in `localStorage` now, which survives a closed
 * tab and a restarted browser, and its lifetime is the one the server actually
 * issues: `JWT_TTL_MINUTES` and the `auth_sessions` row, thirty days by
 * default. The token stays revocable - signing out still deletes the row, and a
 * password reset still ends every device - so "stay signed in" does not mean
 * "cannot be signed out".
 *
 * Two fallbacks, because storage is not always there:
 *
 * - a browser with site data blocked, or a private window in some browsers,
 *   throws on the very first `localStorage` access rather than returning null;
 * - so does a `sessionStorage` access in the same conditions.
 *
 * In that case the session is kept in memory for the life of the page, which is
 * exactly the behaviour there used to be. The app works; it just forgets again.
 */

// The last resort: the page's own memory. Never persisted, never shared.
const memory = new Map<string, string>();

// Probed once per page rather than on every read. `getToken` is called in a
// render path, and a store that works on the first call works for the life of
// the page.
const probed = new Map<string, Storage | null>();

function usable(name: "local" | "session", pick: () => Storage): Storage | null {
  if (typeof window === "undefined") return null;
  if (probed.has(name)) return probed.get(name) ?? null;

  let store: Storage | null = null;
  try {
    const candidate = pick();
    // Availability has to be probed with a real write. Safari with cookies
    // blocked hands back a `Storage` object whose `setItem` throws, so merely
    // finding the property is not enough to trust it.
    const probe = "__saksham_probe__";
    candidate.setItem(probe, "1");
    candidate.removeItem(probe);
    store = candidate;
  } catch {
    store = null;
  }
  probed.set(name, store);
  return store;
}

/** Survives a closed tab. Where the session belongs. */
function durable(): Storage | null {
  return usable("local", () => window.localStorage);
}

/** Dies with the tab. Only read from, to carry an already signed-in parent over. */
function perTab(): Storage | null {
  return usable("session", () => window.sessionStorage);
}

function read(key: string): string | null {
  const store = durable();
  const stored = store ? store.getItem(key) : null;
  if (stored !== null) return stored;

  // Whoever was signed in when this shipped had their token in the per-tab
  // store. Move it across rather than signing them out to fix a bug about
  // being signed out.
  const legacy = perTab()?.getItem(key) ?? null;
  if (legacy !== null) {
    if (store) {
      try {
        store.setItem(key, legacy);
      } catch {
        /* full or blocked: the value is still returned below */
      }
    }
    return legacy;
  }

  return memory.get(key) ?? null;
}

function write(key: string, value: string): void {
  memory.set(key, value);
  try {
    (durable() ?? perTab())?.setItem(key, value);
  } catch {
    // Quota, or a store that only pretended to work. The in-memory copy above
    // keeps this page working; the next visit signs in again.
  }
}

function remove(key: string): void {
  memory.delete(key);
  for (const store of [durable(), perTab()]) {
    try {
      store?.removeItem(key);
    } catch {
      /* nothing to do: the key is gone from memory either way */
    }
  }
}

export function saveAuth(auth: AuthResponse) {
  write(TOKEN_KEY, auth.session_token);
  write(USER_KEY, JSON.stringify(auth.user));
  remove(GUEST_KEY);
}

export function getToken(): string | null {
  return read(TOKEN_KEY);
}

export function getUser(): User | null {
  const raw = read(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    // A half-written or hand-edited value is not worth dead-ending every screen
    // over. Drop it and let the parent sign in again.
    remove(USER_KEY);
    return null;
  }
}

export function saveChild(child: ChildProfile) {
  const next = JSON.stringify(child);
  // Only announce a profile that actually changed. Listeners re-read the child
  // from the server, which saves it again; announcing an identical write would
  // make that loop forever instead of settling once the two agree.
  if (read(CHILD_KEY) === next) return;
  write(CHILD_KEY, next);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("little-learning-session"));
  }
}

export function getChild(): ChildProfile | null {
  const raw = read(CHILD_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ChildProfile;
  } catch {
    remove(CHILD_KEY);
    return null;
  }
}

export function isGuestSession(): boolean {
  return read(GUEST_KEY) === "true" || !getUser();
}

/**
 * Drop the stored child while leaving the parent signed in.
 *
 * Used when the server no longer recognises the child - a profile deleted, or
 * an id from a database this browser has outlived. Keeping it would dead-end
 * every child screen.
 */
export function forgetChild() {
  remove(CHILD_KEY);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("little-learning-session"));
  }
}

export function clearSession() {
  KEYS.forEach(remove);
}
