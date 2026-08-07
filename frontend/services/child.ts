import { api } from "@/services/api";
import { makeGuestChild, seedFinalDemo } from "@/data/prototype";
import type { ChildProfile } from "@/types";
import { getChild, saveChild } from "./session";

export function createChild(session_token: string, name: string, age_group: string, preferred_language: string) {
  return api<ChildProfile>("/children", {
    method: "POST",
    body: JSON.stringify({ session_token, name, age_group, preferred_language })
  }).catch(() => {
    const child = { ...makeGuestChild(), child_id: `local-child-${Date.now()}`, user_id: "local-user", name, age_group, preferred_language };
    saveChild(child);
    return child;
  });
}

export function getProgress(childId: string) {
  return api<{ child: ChildProfile }>(`/progress/${childId}`).catch(() => ({ child: getChild() ?? makeGuestChild() }));
}

export function seedChild(childId: string) {
  return api<ChildProfile>(`/dev/seed/${childId}`, { method: "POST" }).catch(() => {
    const seeded = seedFinalDemo(getChild() ?? makeGuestChild());
    saveChild(seeded);
    return seeded;
  });
}
