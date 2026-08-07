import { api } from "@/services/api";
import type { ChildProfile, CompanionResponse } from "@/types";

const SAFE_GUIDE_TARGETS = new Set([
  "start-practice",
  "continue-adventure",
  "open-rewards",
  "ask-guide",
  "parent-profile",
  "current-map-level",
  "open-certificate"
]);

export function isSafeGuideTarget(targetId: string | null | undefined) {
  return Boolean(targetId && SAFE_GUIDE_TARGETS.has(targetId));
}

export function startCompanionSession(child: ChildProfile | null, isGuest: boolean, currentRoute = "/") {
  return api<CompanionResponse>("/companion/session/start", {
    method: "POST",
    body: JSON.stringify({
      child_id: child?.child_id ?? null,
      current_route: currentRoute,
      is_guest: isGuest
    })
  }).catch(() => {
    const name = child?.name && !isGuest ? `, ${child.name}` : "";
    const message = `Hello${name}! Welcome to Little Learning. Let us begin with Number Kingdom.`;
    return {
      request_id: "local_companion",
      session_id: "local_companion",
      mode: "welcome",
      message,
      avatar: { state: "speaking", message, speak: true, animationEffect: "gentle_hint" },
      guidance: { action: "highlight_element", target_id: "continue-adventure", wait_for_child_click: true },
      next_action: "start_next_level",
      recommendation: {
        kind: "start_next_level",
        path_id: "numbers",
        stage_number: 1,
        target_id: "continue-adventure",
        route: "/levels",
        label: "Continue Adventure"
      }
    } satisfies CompanionResponse;
  });
}
