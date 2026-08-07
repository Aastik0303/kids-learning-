import { api } from "@/services/api";
import { makeGuestChild, seedFinalDemo } from "@/data/prototype";
import type { ChildProfile } from "@/types";
import { getChild, saveChild } from "./session";

export function createChild(session_token: string, name: string, age_group: string, preferred_language: string, age?: number | null) {
  return api<ChildProfile>("/children", {
    method: "POST",
    body: JSON.stringify({ session_token, name, age_group, age, preferred_language })
  }).catch(() => {
    const child = { ...makeGuestChild(), child_id: `local-child-${Date.now()}`, user_id: "local-user", name, age_group, age, learning_mode: age !== null && age !== undefined && age < 3 ? "toddler" as const : "standard" as const, preferred_language };
    saveChild(child);
    return child;
  });
}

export function getProgress(childId: string) {
  return api<{ child: ChildProfile }>(`/progress/${childId}`).catch(() => ({ child: getChild() ?? makeGuestChild() }));
}

export function updateChildProfile(session_token: string | null, child: ChildProfile, updates: { age?: number; age_group?: string; preferred_language?: string; name?: string }) {
  const learning_mode = updates.age !== undefined ? (updates.age < 3 ? "toddler" as const : "standard" as const) : child.learning_mode;
  const localChild = { ...child, ...updates, learning_mode };
  if (!session_token || child.child_id === "guest_child" || child.child_id.startsWith("local-child")) {
    saveChild(localChild);
    return Promise.resolve(localChild);
  }
  return api<ChildProfile>(`/children/${child.child_id}`, {
    method: "PATCH",
    body: JSON.stringify({ session_token, ...updates })
  }).catch(() => {
    saveChild(localChild);
    return localChild;
  });
}

export function seedChild(childId: string) {
  return api<ChildProfile>(`/dev/seed/${childId}`, { method: "POST" }).catch(() => {
    const seeded = seedFinalDemo(getChild() ?? makeGuestChild());
    saveChild(seeded);
    return seeded;
  });
}
