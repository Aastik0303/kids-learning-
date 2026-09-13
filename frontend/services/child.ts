import { api } from "@/services/api";
import { invalidate, shared } from "@/services/cache";
import type { ChildProfile } from "@/types";
import { saveChild } from "./session";

/**
 * Birth month is collected once at onboarding. The class is derived on the
 * server, so nothing here decides which curriculum a child sees.
 */
export function createChild(
  session_token: string,
  name: string,
  birth_year: number,
  birth_month: number,
  preferred_language: string
) {
  return api<ChildProfile>("/children", {
    method: "POST",
    body: JSON.stringify({ session_token, name, birth_year, birth_month, preferred_language })
  }).then((child) => {
    saveChild(child);
    forgetChildren();
    return child;
  });
}

/**
 * The children belonging to the signed-in parent.
 *
 * Nothing is stored client-side across a login: the session only holds a token,
 * so the child has to be fetched back from the server before any screen can
 * show a class, subjects or progress.
 */
export function listChildren(session_token: string) {
  // Every screen mounts `useActiveChild`, and so does the shell around it, so
  // one navigation asked for the same list three or four times. They share one
  // read; anything that changes the child - finishing a lesson, editing the
  // profile - calls `forgetChildren`.
  return shared(`children:${session_token}`, () =>
    // The standard bearer shape. This used to be a bespoke `X-Demo-Session`
    // header from the prototype; the server accepts both, so the rename here
    // signs nobody out.
    api<ChildProfile[]>("/children", { headers: { Authorization: `Bearer ${session_token}` } })
  );
}

/** The stored child has changed on the server. Drop the shared read. */
export function forgetChildren() {
  invalidate("children");
}

/** Load the parent's first child into the session. Returns null when there is none yet. */
export async function loadActiveChild(session_token: string): Promise<ChildProfile | null> {
  const children = await listChildren(session_token);
  const child = children[0] ?? null;
  if (child) saveChild(child);
  return child;
}

export function getProgress(childId: string) {
  // Never shared: this is the call a finished lesson makes to find out what it
  // earned, and a cached answer there would show the stars from before it.
  return api<{ child: ChildProfile }>(`/progress/${childId}`).then((progress) => {
    forgetChildren();
    return progress;
  });
}

export function updateChildProfile(
  session_token: string,
  child: ChildProfile,
  updates: { name?: string; birth_year?: number; birth_month?: number; preferred_language?: string }
) {
  return api<ChildProfile>(`/children/${child.child_id}`, {
    method: "PATCH",
    body: JSON.stringify({ session_token, ...updates })
  }).then((updated) => {
    saveChild(updated);
    forgetChildren();
    return updated;
  });
}
