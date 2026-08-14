import {
  GUIDE_ACTION_TYPES,
  GUIDE_STRATEGIES,
  GUIDE_VISUAL_ACTION_TYPES,
  type GuideActionType,
  type GuideResponse,
  type GuideStrategy,
  type GuideVisualActionType,
} from "@/types/guide";
import type { AvatarEffect, AvatarState } from "@/types/domain";
import { isSafeRoute } from "@/navigation/routes";

/**
 * ═══ THE SAFETY BOUNDARY (spec section 10) ═══
 *
 * Model output crosses into UI control here and nowhere else. The rule
 * this file enforces:
 *
 *   AI response → schema validation → action allowlist → target allowlist
 *                → GuideActionExecutor → UI
 *
 * Anything the model emits that is not an exact member of a closed union,
 * or that names a target which is not currently registered and on screen,
 * is dropped. Unknown fields are discarded rather than passed through.
 * There is no path from model output to arbitrary code, arbitrary routes,
 * or component manipulation.
 *
 * Failure is always "degrade to a safe default", never "throw" — a
 * malformed response must leave a child with a friendly avatar, not a
 * broken screen.
 */

const AVATAR_STATES: readonly AvatarState[] = [
  "idle",
  "waving",
  "listening",
  "thinking",
  "speaking",
  "happy",
  "celebrating",
  "encouraging",
  "storytelling",
  "sleeping",
  "error_fallback",
];

const AVATAR_EFFECTS: readonly AvatarEffect[] = [
  "star_burst",
  "confetti",
  "level_unlock",
  "reward_chest",
  "gentle_hint",
  "story_transition",
  "certificate_celebration",
  "sparkle",
  "bounce",
  "rainbow",
  "pulse",
  "none",
];

/** Child-facing speech never legitimately needs to be longer than this. */
const MAX_MESSAGE_LENGTH = 320;

/**
 * Patterns that must never survive into avatar speech. The backend runs
 * its own keyword safety filter; this is defence in depth on the client,
 * covering injection-shaped output rather than content policy.
 */
const UNSAFE_PATTERNS: readonly RegExp[] = [
  /<\s*script/i,
  /javascript:/i,
  /https?:\/\//i,
  /\bfunction\s*\(/i,
  /[{}<>]/,
];

export type ValidationRejection = {
  field: string;
  reason: string;
};

export type ValidatedGuide = {
  response: GuideResponse;
  /** Everything that was stripped, for analytics and debugging. */
  rejections: ValidationRejection[];
};

export type ValidationContext = {
  /** Target ids currently registered and on screen. */
  allowedTargets: readonly string[];
  /** Subset that may receive visual treatments. */
  allowedVisualTargets: readonly string[];
  /** Action types this screen offered. The model may not exceed them. */
  offeredActions: readonly GuideActionType[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

/** Strip anything that looks like markup, code or a link, then clamp. */
function sanitizeMessage(raw: string, rejections: ValidationRejection[]): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";

  for (const pattern of UNSAFE_PATTERNS) {
    if (pattern.test(trimmed)) {
      rejections.push({ field: "message", reason: `matched unsafe pattern ${pattern.source}` });
      return "";
    }
  }

  if (trimmed.length > MAX_MESSAGE_LENGTH) {
    rejections.push({ field: "message", reason: "exceeded max length" });
    return `${trimmed.slice(0, MAX_MESSAGE_LENGTH).trimEnd()}…`;
  }

  return trimmed;
}

/**
 * Validate a raw guide response against the closed unions and the live
 * target allowlist. Always returns a usable response.
 */
export function validateGuideResponse(
  raw: unknown,
  context: ValidationContext,
  fallbackMessage: string,
): ValidatedGuide {
  const rejections: ValidationRejection[] = [];

  if (!isRecord(raw)) {
    return {
      response: safeFallback(fallbackMessage),
      rejections: [{ field: "root", reason: "response was not an object" }],
    };
  }

  // ── message ──────────────────────────────────────────────────────────
  const message = sanitizeMessage(asString(raw.message), rejections) || fallbackMessage;

  // ── strategy ─────────────────────────────────────────────────────────
  const strategy = oneOf<GuideStrategy>(raw.strategy, GUIDE_STRATEGIES, "none");
  if (raw.strategy !== undefined && raw.strategy !== strategy) {
    rejections.push({ field: "strategy", reason: `unknown strategy ${String(raw.strategy)}` });
  }

  // ── avatar ───────────────────────────────────────────────────────────
  const rawAvatar = isRecord(raw.avatar) ? raw.avatar : {};
  const avatarState = oneOf<AvatarState>(rawAvatar.state, AVATAR_STATES, "idle");
  const avatarEffect =
    rawAvatar.animationEffect === null || rawAvatar.animationEffect === undefined
      ? null
      : oneOf<AvatarEffect>(rawAvatar.animationEffect, AVATAR_EFFECTS, "none");

  // ── ui_action ────────────────────────────────────────────────────────
  const rawUi = isRecord(raw.ui_action) ? raw.ui_action : {};
  let actionType = oneOf<GuideActionType>(rawUi.type, GUIDE_ACTION_TYPES, "none");

  // The model may not invent an action the screen never offered.
  if (actionType !== "none" && !context.offeredActions.includes(actionType)) {
    rejections.push({ field: "ui_action.type", reason: `${actionType} was not offered by screen` });
    actionType = "none";
  }

  let target: string | null = typeof rawUi.target === "string" ? rawUi.target : null;

  if (target !== null) {
    const targetIsAllowed =
      actionType === "open_safe_route"
        ? // Route actions are checked against the route allowlist instead.
          isSafeRoute(target)
        : context.allowedTargets.includes(target);

    if (!targetIsAllowed) {
      rejections.push({
        field: "ui_action.target",
        reason: `target "${target}" is not registered on this screen`,
      });
      target = null;
      // An action that needs a target but lost it becomes a no-op.
      if (needsTarget(actionType)) actionType = "none";
    }
  } else if (needsTarget(actionType)) {
    rejections.push({ field: "ui_action.target", reason: `${actionType} requires a target` });
    actionType = "none";
  }

  // ── visual_action ────────────────────────────────────────────────────
  const rawVisual = isRecord(raw.visual_action) ? raw.visual_action : {};
  let visualType = oneOf<GuideVisualActionType>(
    rawVisual.type,
    GUIDE_VISUAL_ACTION_TYPES,
    "none",
  );

  const requestedVisualTargets = asStringArray(rawVisual.targets);
  const visualTargets = requestedVisualTargets.filter((id) =>
    context.allowedVisualTargets.includes(id),
  );

  if (requestedVisualTargets.length !== visualTargets.length) {
    rejections.push({
      field: "visual_action.targets",
      reason: `dropped ${requestedVisualTargets.length - visualTargets.length} unregistered target(s)`,
    });
  }

  if (visualType !== "none" && visualTargets.length === 0) {
    // Nothing survivable to point at — do not animate at random.
    visualType = "none";
  }

  return {
    response: {
      message,
      strategy,
      avatar: {
        state: avatarState,
        message: sanitizeMessage(asString(rawAvatar.message), rejections) || message,
        speak: typeof rawAvatar.speak === "boolean" ? rawAvatar.speak : true,
        animationEffect: avatarEffect,
        durationMs:
          typeof rawAvatar.durationMs === "number" && Number.isFinite(rawAvatar.durationMs)
            ? Math.min(Math.max(rawAvatar.durationMs, 0), 10_000)
            : null,
      },
      ui_action: { type: actionType, target },
      visual_action: { type: visualType, targets: visualTargets },
      next_expected_event: asString(raw.next_expected_event) || "wait_for_child",
    },
    rejections,
  };
}

function needsTarget(action: GuideActionType): boolean {
  return (
    action === "highlight" ||
    action === "scroll_to" ||
    action === "show_tooltip" ||
    action === "wait_for_click" ||
    action === "open_safe_route"
  );
}

/** What the avatar says when the model fails us entirely. */
export function safeFallback(message: string): GuideResponse {
  return {
    message,
    strategy: "none",
    avatar: {
      state: "encouraging",
      message,
      speak: true,
      animationEffect: null,
      durationMs: null,
    },
    ui_action: { type: "none", target: null },
    visual_action: { type: "none", targets: [] },
    next_expected_event: "wait_for_child",
  };
}
