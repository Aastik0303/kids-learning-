import { create } from "zustand";

import type { AvatarEffect, AvatarState } from "@/types/domain";
import type { GuideStrategy, GuideUiAction, GuideVisualAction } from "@/types/guide";

/**
 * State of the global AI companion layer (spec section 9). The avatar is
 * not a screen — it is this store plus a fixed overlay, so it survives
 * every navigation inside the child experience.
 */

export type DoubtPhase =
  | "idle"
  /** Lesson frozen, avatar inviting the child to speak. */
  | "asking"
  /** Microphone open, capturing the doubt. */
  | "listening"
  /** Waiting on the guide agent. */
  | "thinking"
  /** Explanation delivered, offering resume or re-explain. */
  | "explaining";

export type GuideMessage = {
  id: string;
  role: "guide" | "child";
  text: string;
  at: number;
};

type GuideState = {
  /** What the avatar is currently saying. */
  message: string;
  avatarState: AvatarState;
  effect: AvatarEffect | null;
  strategy: GuideStrategy;
  isThinking: boolean;

  /** Pending action awaiting execution by GuideActionExecutor. */
  pendingUiAction: GuideUiAction | null;
  pendingVisualAction: GuideVisualAction | null;

  /** Targets currently highlighted, keyed by target id → step index. */
  activeHighlights: Record<string, number>;

  /** Hand Raise / Doubt Mode. */
  doubtPhase: DoubtPhase;
  /** Short rolling transcript, sent as guide conversation context. */
  conversation: GuideMessage[];

  /** True while the avatar dock is expanded into a chat panel. */
  isDockOpen: boolean;

  say: (input: {
    message: string;
    avatarState?: AvatarState;
    effect?: AvatarEffect | null;
    strategy?: GuideStrategy;
  }) => void;
  setThinking: (value: boolean) => void;
  setAvatarState: (state: AvatarState) => void;
  queueUiAction: (action: GuideUiAction | null) => void;
  queueVisualAction: (action: GuideVisualAction | null) => void;
  clearPendingActions: () => void;
  setHighlights: (targets: string[]) => void;
  clearHighlights: () => void;
  setDoubtPhase: (phase: DoubtPhase) => void;
  appendMessage: (role: GuideMessage["role"], text: string) => void;
  clearConversation: () => void;
  setDockOpen: (open: boolean) => void;
  reset: () => void;
};

let messageCounter = 0;

/** Conversation context sent to the backend is capped at 8 turns. */
const MAX_CONVERSATION = 8;

export const useGuideStore = create<GuideState>((set) => ({
  message: "",
  avatarState: "idle",
  effect: null,
  strategy: "none",
  isThinking: false,
  pendingUiAction: null,
  pendingVisualAction: null,
  activeHighlights: {},
  doubtPhase: "idle",
  conversation: [],
  isDockOpen: false,

  say({ message, avatarState, effect, strategy }) {
    messageCounter += 1;
    set((state) => ({
      message,
      avatarState: avatarState ?? "speaking",
      effect: effect ?? null,
      strategy: strategy ?? state.strategy,
      isThinking: false,
      conversation: [
        ...state.conversation,
        { id: `g${messageCounter}`, role: "guide" as const, text: message, at: Date.now() },
      ].slice(-MAX_CONVERSATION),
    }));
  },

  setThinking(value) {
    set({ isThinking: value, ...(value ? { avatarState: "thinking" as AvatarState } : {}) });
  },

  setAvatarState(avatarState) {
    set({ avatarState });
  },

  queueUiAction(action) {
    set({ pendingUiAction: action });
  },

  queueVisualAction(action) {
    set({ pendingVisualAction: action });
  },

  clearPendingActions() {
    set({ pendingUiAction: null, pendingVisualAction: null });
  },

  /**
   * Highlights carry their sequence index so `highlight_sequence` can
   * stagger the animation the way the web build's CSS delays did.
   */
  setHighlights(targets) {
    const next: Record<string, number> = {};
    targets.forEach((target, index) => {
      next[target] = index;
    });
    set({ activeHighlights: next });
  },

  clearHighlights() {
    set({ activeHighlights: {} });
  },

  setDoubtPhase(doubtPhase) {
    set({ doubtPhase });
  },

  appendMessage(role, text) {
    if (!text.trim()) return;
    messageCounter += 1;
    set((state) => ({
      conversation: [
        ...state.conversation,
        { id: `${role[0]}${messageCounter}`, role, text, at: Date.now() },
      ].slice(-MAX_CONVERSATION),
    }));
  },

  clearConversation() {
    set({ conversation: [] });
  },

  setDockOpen(isDockOpen) {
    set({ isDockOpen });
  },

  reset() {
    set({
      message: "",
      avatarState: "idle",
      effect: null,
      strategy: "none",
      isThinking: false,
      pendingUiAction: null,
      pendingVisualAction: null,
      activeHighlights: {},
      doubtPhase: "idle",
      conversation: [],
      isDockOpen: false,
    });
  },
}));
