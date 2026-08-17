import { api } from "@/services/api";
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
  return api<ChildProfile[]>("/children", {
    headers: { "X-Demo-Session": session_token }
  });
}

/** Load the parent's first child into the session. Returns null when there is none yet. */
export async function loadActiveChild(session_token: string): Promise<ChildProfile | null> {
  const children = await listChildren(session_token);
  const child = children[0] ?? null;
  if (child) saveChild(child);
  return child;
}

export function getProgress(childId: string) {
  return api<{ child: ChildProfile }>(`/progress/${childId}`);
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
    return updated;
  });
}

export function seedChild(childId: string) {
  return api<ChildProfile>(`/dev/seed/${childId}`, { method: "POST" }).then((child) => {
    saveChild(child);
    return child;
  });
}
