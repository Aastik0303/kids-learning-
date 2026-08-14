import type { View } from "react-native";

import { track } from "@/services/analytics/analytics";
import { navigationRef } from "@/navigation/navigationRef";
import { SAFE_ROUTES, isSafeRoute } from "@/navigation/routes";
import { useGuideStore } from "@/store/guideStore";
import { useUiStore } from "@/store/uiStore";
import type { GuideUiAction, GuideVisualAction } from "@/types/guide";
import type { RegisteredTarget } from "@/ai/GuideTargetRegistry";

/**
 * Executes guide actions that have already cleared `guideSchema.ts`.
 *
 * This module performs the *effect* only. It re-checks the target
 * allowlist anyway — validation and execution are separated so that a
 * future caller cannot accidentally bypass the check by calling the
 * executor directly.
 */

export type ExecutorDeps = {
  /** Look up a registered, currently-mounted target. */
  getTarget: (id: string) => RegisteredTarget | undefined;
  /** Scrolls a target into view. Supplied by whichever screen owns a scroller. */
  scrollToTarget?: (target: RegisteredTarget) => void;
  /** Re-speaks the current instruction. */
  repeatInstruction?: () => void;
  /** Opens the hint affordance for the current activity. */
  showHint?: () => void;
};

export type ExecutionResult = {
  executed: boolean;
  reason?: string;
};

/**
 * Highlights are applied by writing target ids into the guide store; the
 * `GuideHighlight` wrapper each target renders inside subscribes and
 * animates itself. Nothing here touches a component instance directly.
 */
export function executeUiAction(
  action: GuideUiAction,
  deps: ExecutorDeps,
): ExecutionResult {
  const guide = useGuideStore.getState();
  const ui = useUiStore.getState();

  switch (action.type) {
    case "none":
      return { executed: false, reason: "no action" };

    case "highlight": {
      if (!action.target) return reject("highlight without target", action.type);
      if (!deps.getTarget(action.target)) {
        return reject("target not mounted", action.type);
      }
      guide.setHighlights([action.target]);
      track("guide_action_executed", { action: action.type, target: action.target });
      return { executed: true };
    }

    case "scroll_to": {
      if (!action.target) return reject("scroll_to without target", action.type);
      const target = deps.getTarget(action.target);
      if (!target) return reject("target not mounted", action.type);
      deps.scrollToTarget?.(target);
      guide.setHighlights([action.target]);
      track("guide_action_executed", { action: action.type, target: action.target });
      return { executed: true };
    }

    case "show_tooltip": {
      if (!action.target) return reject("show_tooltip without target", action.type);
      if (!deps.getTarget(action.target)) return reject("target not mounted", action.type);
      guide.setHighlights([action.target]);
      track("guide_action_executed", { action: action.type, target: action.target });
      return { executed: true };
    }

    case "wait_for_click": {
      if (!action.target) return reject("wait_for_click without target", action.type);
      if (!deps.getTarget(action.target)) return reject("target not mounted", action.type);
      // Point at it and hand control back to the child. Input stays live —
      // "wait" means the guide stops talking, not that the UI freezes.
      guide.setHighlights([action.target]);
      guide.setAvatarState("encouraging");
      track("guide_action_executed", { action: action.type, target: action.target });
      return { executed: true };
    }

    case "repeat_instruction": {
      deps.repeatInstruction?.();
      track("guide_action_executed", { action: action.type, target: null });
      return { executed: true };
    }

    case "show_hint": {
      deps.showHint?.();
      track("guide_action_executed", { action: action.type, target: null });
      return { executed: true };
    }

    case "open_safe_route": {
      // Second gate. `isSafeRoute` already ran during validation; running
      // it again means no caller can reach navigation without passing it.
      if (!isSafeRoute(action.target)) {
        return reject(`route "${action.target}" not in allowlist`, action.type);
      }
      if (!navigationRef.isReady()) {
        return reject("navigation not ready", action.type);
      }

      const route = SAFE_ROUTES[action.target];
      ui.setInputLocked(false);
      navigationRef.navigate(route.stack, {
        screen: route.screen,
        params: route.params,
      } as never);
      track("guide_action_executed", { action: action.type, target: action.target });
      return { executed: true };
    }
  }
}

function reject(reason: string, action: string): ExecutionResult {
  track("guide_action_rejected", { reason, action });
  return { executed: false, reason };
}

/**
 * Visual actions decorate registered targets. Every variant resolves to
 * "write ids into the store"; the difference is purely how the wrapper
 * animates, which keeps this side effect-free and testable.
 */
export function executeVisualAction(
  action: GuideVisualAction,
  deps: ExecutorDeps,
): ExecutionResult {
  const guide = useGuideStore.getState();

  if (action.type === "none" || action.targets.length === 0) {
    guide.clearHighlights();
    return { executed: false, reason: "no visual action" };
  }

  const mounted = action.targets.filter((id) => deps.getTarget(id));
  if (mounted.length === 0) {
    return reject("no visual targets mounted", action.type);
  }

  guide.setHighlights(mounted);
  track("guide_action_executed", { action: action.type, target: mounted.join(",") });
  return { executed: true };
}

/**
 * Measure a target on screen. Used by the highlight overlay so a pointer
 * can be drawn at the right place without the target itself knowing.
 */
export function measureTarget(
  target: RegisteredTarget,
): Promise<{ x: number; y: number; width: number; height: number } | null> {
  return new Promise((resolve) => {
    const node: View | null = target.ref.current;
    if (!node) {
      resolve(null);
      return;
    }
    node.measureInWindow((x, y, width, height) => {
      if ([x, y, width, height].some((value) => !Number.isFinite(value))) {
        resolve(null);
        return;
      }
      resolve({ x, y, width, height });
    });
  });
}
