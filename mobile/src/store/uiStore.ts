import { create } from "zustand";

/**
 * Transient app-shell state: connectivity, celebration overlays and the
 * parent gate. Nothing here is persisted.
 */

export type CelebrationKind =
  | "stars"
  | "level_complete"
  | "world_complete"
  | "reward_unlocked"
  | "certificate";

export type Celebration = {
  kind: CelebrationKind;
  title: string;
  subtitle?: string;
  stars?: number;
};

type UiState = {
  isOnline: boolean;
  /** Set when the backend is unreachable even though the device has a network. */
  isBackendReachable: boolean;
  celebration: Celebration | null;
  /** Parent area stays locked until the gate is passed this session. */
  isParentUnlocked: boolean;
  /** Blocks child taps during a scripted guide moment. */
  isInputLocked: boolean;
  /**
   * The corner avatar is off.
   *
   * Set by the class, which stands the same panda in the middle of the screen
   * and holds the lesson on a board in its paws. Two of the same character on
   * one screen is one too many for a three-year-old, who looks at whichever
   * moved last.
   */
  isDockHidden: boolean;
  toast: string | null;

  setOnline: (value: boolean) => void;
  setBackendReachable: (value: boolean) => void;
  celebrate: (celebration: Celebration) => void;
  dismissCelebration: () => void;
  unlockParent: () => void;
  lockParent: () => void;
  setInputLocked: (value: boolean) => void;
  setDockHidden: (value: boolean) => void;
  showToast: (message: string) => void;
  clearToast: () => void;
};

export const useUiStore = create<UiState>((set) => ({
  isOnline: true,
  isBackendReachable: true,
  celebration: null,
  isParentUnlocked: false,
  isInputLocked: false,
  isDockHidden: false,
  toast: null,

  setOnline(isOnline) {
    set({ isOnline });
  },

  setBackendReachable(isBackendReachable) {
    set({ isBackendReachable });
  },

  celebrate(celebration) {
    set({ celebration });
  },

  dismissCelebration() {
    set({ celebration: null });
  },

  unlockParent() {
    set({ isParentUnlocked: true });
  },

  /** Called on app background so the gate re-arms. */
  lockParent() {
    set({ isParentUnlocked: false });
  },

  setInputLocked(isInputLocked) {
    set({ isInputLocked });
  },

  setDockHidden(isDockHidden) {
    set({ isDockHidden });
  },

  showToast(toast) {
    set({ toast });
  },

  clearToast() {
    set({ toast: null });
  },
}));
