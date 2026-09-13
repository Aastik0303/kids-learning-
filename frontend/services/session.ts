"use client";

import type { AuthResponse, ChildProfile, User } from "@/types";

const TOKEN_KEY = "saksham.session_token";
const USER_KEY = "saksham.user";
const CHILD_KEY = "saksham.child";
const GUEST_KEY = "saksham.guest";

const KEYS = [TOKEN_KEY, USER_KEY, CHILD_KEY, GUEST_KEY];

/**
 * What each key used to be called.
 *
 * These were `demo_*` from when this was a prototype, and the names outlived
 * that. Renaming them on its own would sign out every parent who is signed in
 * right now, so a value found under the old name is moved across on the first
 * read and the old key is dropped. Nothing has to be done by anyone, and after
 * a visit each browser holds only the new names.
 */
const LEGACY_KEYS: Record<string, string> = {
  [TOKEN_KEY]: "demo_session_token",
  [USER_KEY]: "demo_user",
  [CHILD_KEY]: "demo_child",
  [GUEST_KEY]: "demo_guest_active"
};

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

/** Every place a value for this key may still be sitting, newest first. */
function candidates(key: string): [Storage | null, string][] {
  const legacy = LEGACY_KEYS[key];
  const stores: [Storage | null, string][] = [
    [durable(), key],
    [perTab(), key]
  ];
  // Whoever was signed in when this shipped had their token in the per-tab
  // store, under the old name. Move it across rather than signing them out to
  // fix a bug about being signed out.
  if (legacy) stores.push([durable(), legacy], [perTab(), legacy]);
  return stores;
}

function read(key: string): string | null {
  for (const [store, name] of candidates(key)) {
    let found: string | null = null;
    try {
      found = store?.getItem(name) ?? null;
    } catch {
      continue;
    }
    if (found === null) continue;

    // Found somewhere other than where it belongs: put it where it belongs and
    // clear the old copy, so this migration happens once per browser.
    if (store !== durable() || name !== key) {
      try {
        durable()?.setItem(key, found);
        if (name !== key) store?.removeItem(name);
      } catch {
        /* full or blocked: the value is still returned below */
      }
    }
    return found;
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
  // Including anything left under the old names, so signing out on a browser
  // that has not yet been migrated actually signs it out.
  Object.values(LEGACY_KEYS).forEach(remove);
}
