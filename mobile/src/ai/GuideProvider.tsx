import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

import {
  buildGuideRequest,
  LESSON_ACTIONS,
  NAVIGATION_ACTIONS,
  type DispatchContext,
} from "@/ai/GuideEventDispatcher";
import {
  executeUiAction,
  executeVisualAction,
  type ExecutorDeps,
} from "@/ai/GuideActionExecutor";
import { useGuideTargetRegistry } from "@/ai/GuideTargetRegistry";
import { safeFallback, validateGuideResponse } from "@/ai/guideSchema";
import {
  shouldCallAgent,
  staticEncouragement,
  staticPraise,
  type AppGuideEvent,
  type EventSurface,
} from "@/ai/guideEvents";
import { isEnabled } from "@/config/featureFlags";
import { guideApi } from "@/services/api/guideApi";
import { track } from "@/services/analytics/analytics";
import { currentRouteName } from "@/navigation/navigationRef";
import { useChildStore } from "@/store/childStore";
import { useGuideStore } from "@/store/guideStore";
import { useSessionStore } from "@/store/sessionStore";
import { voiceController } from "@/features/voice/VoiceController";
import type { GuideActionType } from "@/types/guide";

/**
 * The global AI companion layer (spec section 8).
 *
 * The guide is not a screen. It is this provider plus a fixed overlay, so
 * the avatar, its speech, hand-raise and highlights persist across every
 * navigation inside the child experience.
 *
 * Flow for one dispatch:
 *
 *   dispatch(event) → build request from live app state
 *                   → POST /agent/guide
 *                   → validate against action + target allowlists
 *                   → execute the surviving action
 *                   → speak the message
 */

export type DispatchOptions = {
  surface?: EventSurface;
  /** What the child just answered, when relevant. */
  childAnswer?: string | null;
  /** Overrides the screen's default action allowlist. */
  offeredActions?: readonly GuideActionType[];
  /** Suppress TTS for this dispatch (e.g. a silent background prefetch). */
  silent?: boolean;
  /** Extra deps for actions this screen can honour. */
  deps?: Partial<ExecutorDeps>;
};

type GuideContextValue = {
  dispatch: (event: AppGuideEvent, options?: DispatchOptions) => Promise<void>;
  /** Speak a line without consulting the agent. */
  say: (message: string, options?: { speak?: boolean }) => Promise<void>;
  /** Re-read the current activity prompt aloud. */
  repeatCurrent: () => Promise<void>;
};

const GuideContext = createContext<GuideContextValue | null>(null);

export function GuideProvider({ children }: { children: ReactNode }) {
  const registry = useGuideTargetRegistry();
  // Guards against two dispatches racing — the later one wins.
  const inFlight = useRef<AbortController | null>(null);

  const speak = useCallback(async (message: string) => {
    const child = useChildStore.getState().activeChild;
    await voiceController.speak(message, child?.preferred_language);
  }, []);

  const say = useCallback(
    async (message: string, options?: { speak?: boolean }) => {
      useGuideStore.getState().say({ message, avatarState: "speaking" });
      if (options?.speak !== false) await speak(message);
      useGuideStore.getState().setAvatarState("idle");
    },
    [speak],
  );

  const repeatCurrent = useCallback(async () => {
    const activity = useSessionStore.getState().activity;
    if (!activity) return;
    await say(activity.speech || activity.prompt);
  }, [say]);

  const dispatch = useCallback(
    async (event: AppGuideEvent, options: DispatchOptions = {}) => {
      const guide = useGuideStore.getState();
      const session = useSessionStore.getState();
      const child = useChildStore.getState().activeChild;
      const surface = options.surface ?? (session.kind === "practice" ? "practice" : "lesson");

      // ── Fast path: no model call needed ──────────────────────────────
      if (!shouldCallAgent(event, session.attempt)) {
        if (event === "ANSWER_CORRECT") {
          const message = staticPraise(session.attempt + (session.activity?.id.length ?? 0));
          guide.say({ message, avatarState: "celebrating", strategy: "celebrate" });
          if (!options.silent) await speak(message);
          guide.setAvatarState("idle");
        }
        return;
      }

      // ── Build the request from live state ────────────────────────────
      const offeredActions =
        options.offeredActions ??
        (session.activity ? LESSON_ACTIONS : NAVIGATION_ACTIONS);

      const availableTargets = registry.targetIds();
      const availableVisualTargets = isEnabled("guideVisualActions")
        ? registry.visualTargetIds()
        : [];

      const context: DispatchContext = {
        event,
        surface,
        child,
        sessionId: session.sessionId,
        routeName: currentRouteName(),
        screen: currentRouteName(),
        feature: surface,
        activity: session.activity,
        attempt: session.attempt,
        childAnswer: options.childAnswer ?? null,
        recentAnswers: session.recentAnswers,
        sessionStars: session.sessionStars,
        pathId: session.pathId,
        stageNumber: session.stageNumber || null,
        conversation: guide.conversation.map((turn) => ({
          role: turn.role === "guide" ? "assistant" : "user",
          content: turn.text,
        })),
        availableTargets,
        availableVisualTargets,
        offeredActions,
      };

      const request = buildGuideRequest(context);
      if (!request) return;

      // ── Call the agent ───────────────────────────────────────────────
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;

      guide.setThinking(true);

      let raw: unknown;
      try {
        raw = await guideApi.ask(request, controller.signal);
      } catch {
        // The agent is unreachable or slow. A child cannot be left with a
        // silent avatar, so fall back to a deterministic encouraging line.
        const fallback =
          event === "ANSWER_INCORRECT"
            ? staticEncouragement(session.attempt)
            : "Let us keep going!";
        const response = safeFallback(fallback);
        guide.say({
          message: response.message,
          avatarState: response.avatar.state,
          strategy: "none",
        });
        if (!options.silent) await speak(response.message);
        guide.setAvatarState("idle");
        return;
      } finally {
        if (inFlight.current === controller) inFlight.current = null;
        useGuideStore.getState().setThinking(false);
      }

      if (controller.signal.aborted) return;

      // ── Validate before anything touches the UI ──────────────────────
      const { response, rejections } = validateGuideResponse(
        raw,
        {
          allowedTargets: availableTargets,
          allowedVisualTargets: availableVisualTargets,
          offeredActions,
        },
        "Let us keep going!",
      );

      rejections.forEach((rejection) => {
        track("guide_action_rejected", { reason: rejection.reason, action: rejection.field });
      });

      // ── Apply ────────────────────────────────────────────────────────
      useGuideStore.getState().say({
        message: response.message,
        avatarState: response.avatar.state,
        effect: response.avatar.animationEffect ?? null,
        strategy: response.strategy,
      });

      const deps: ExecutorDeps = {
        getTarget: registry.get,
        repeatInstruction: () => void repeatCurrent(),
        ...options.deps,
      };

      executeVisualAction(response.visual_action, deps);
      executeUiAction(response.ui_action, deps);

      if (!options.silent && response.avatar.speak !== false) {
        await speak(response.message);
      }
      useGuideStore.getState().setAvatarState("idle");
    },
    [registry, repeatCurrent, speak],
  );

  const value = useMemo<GuideContextValue>(
    () => ({ dispatch, say, repeatCurrent }),
    [dispatch, say, repeatCurrent],
  );

  return <GuideContext.Provider value={value}>{children}</GuideContext.Provider>;
}

export function useGuide(): GuideContextValue {
  const value = useContext(GuideContext);
  if (!value) {
    throw new Error("useGuide must be used inside <GuideProvider>");
  }
  return value;
}
