import { create } from "zustand";

import { kv, storageKeys } from "@/services/storage/kv";
import type { RenderableActivity } from "@/types/activity";
import type { LearningMode } from "@/types/domain";

/**
 * The live learning session. This is the state that Hand Raise has to
 * freeze and restore exactly (spec section 13), and that app
 * background/foreground has to survive (spec section 20).
 */

export type SessionKind = "lesson" | "practice" | "toddler";

export type SessionSnapshot = {
  kind: SessionKind;
  /** Backend session id — `session_id` or `practice_session_id`. */
  sessionId: string;
  childId: string;
  pathId: string;
  stageNumber: number;
  activityId: string | null;
  attempt: number;
  learningMode: LearningMode;
  savedAt: number;
};

type SessionState = {
  kind: SessionKind | null;
  sessionId: string | null;
  childId: string | null;
  pathId: string | null;
  stageNumber: number;
  activity: RenderableActivity | null;
  attempt: number;
  sessionStars: number;
  /** Answers the child has already tried on this activity. */
  recentAnswers: string[];
  isSubmitting: boolean;

  /**
   * Hand Raise pauses the lesson. The activity stays mounted and the
   * snapshot below is what "resume the exact paused step" restores from.
   */
  isPaused: boolean;
  pausedAt: SessionSnapshot | null;

  begin: (input: {
    kind: SessionKind;
    sessionId: string;
    childId: string;
    pathId: string;
    stageNumber: number;
    learningMode: LearningMode;
  }) => void;
  setActivity: (activity: RenderableActivity | null) => void;
  recordAttempt: (answer: string) => void;
  resetAttempts: () => void;
  addStars: (stars: number) => void;
  setSubmitting: (value: boolean) => void;

  pause: () => void;
  resume: () => void;

  persist: () => Promise<void>;
  loadResumable: () => Promise<SessionSnapshot | null>;
  clearResumable: () => Promise<void>;
  end: () => void;
};

export const useSessionStore = create<SessionState>((set, get) => ({
  kind: null,
  sessionId: null,
  childId: null,
  pathId: null,
  stageNumber: 0,
  activity: null,
  attempt: 0,
  sessionStars: 0,
  recentAnswers: [],
  isSubmitting: false,
  isPaused: false,
  pausedAt: null,

  begin({ kind, sessionId, childId, pathId, stageNumber, learningMode }) {
    set({
      kind,
      sessionId,
      childId,
      pathId,
      stageNumber,
      attempt: 0,
      recentAnswers: [],
      isPaused: false,
      pausedAt: null,
      isSubmitting: false,
    });
    void kv.set(storageKeys.resumableSession, {
      kind,
      sessionId,
      childId,
      pathId,
      stageNumber,
      activityId: null,
      attempt: 0,
      learningMode,
      savedAt: Date.now(),
    } satisfies SessionSnapshot);
  },

  setActivity(activity) {
    // A new activity resets the per-question attempt counter and history.
    const isNewQuestion = activity?.id !== get().activity?.id;
    set({
      activity,
      ...(isNewQuestion ? { attempt: 0, recentAnswers: [] } : {}),
    });
    void get().persist();
  },

  recordAttempt(answer) {
    set((state) => ({
      attempt: state.attempt + 1,
      // Keep the last few only — this feeds the guide's context payload.
      recentAnswers: [...state.recentAnswers, answer].slice(-4),
    }));
  },

  resetAttempts() {
    set({ attempt: 0, recentAnswers: [] });
  },

  addStars(stars) {
    if (stars <= 0) return;
    set((state) => ({ sessionStars: state.sessionStars + stars }));
  },

  setSubmitting(value) {
    set({ isSubmitting: value });
  },

  /**
   * Freeze. Deliberately does NOT clear the activity — the child must come
   * back to the same question, not a reloaded one.
   */
  pause() {
    const state = get();
    if (state.isPaused || !state.sessionId) return;
    set({
      isPaused: true,
      pausedAt: {
        kind: state.kind ?? "lesson",
        sessionId: state.sessionId,
        childId: state.childId ?? "",
        pathId: state.pathId ?? "",
        stageNumber: state.stageNumber,
        activityId: state.activity?.id ?? null,
        attempt: state.attempt,
        learningMode: "standard",
        savedAt: Date.now(),
      },
    });
  },

  resume() {
    set({ isPaused: false, pausedAt: null });
  },

  async persist() {
    const state = get();
    if (!state.sessionId || !state.kind) return;
    await kv.set(storageKeys.resumableSession, {
      kind: state.kind,
      sessionId: state.sessionId,
      childId: state.childId ?? "",
      pathId: state.pathId ?? "",
      stageNumber: state.stageNumber,
      activityId: state.activity?.id ?? null,
      attempt: state.attempt,
      learningMode: "standard",
      savedAt: Date.now(),
    } satisfies SessionSnapshot);
  },

  /**
   * Offers a resume only if the session is recent. A day-old pointer is
   * more confusing than helpful for a small child.
   */
  async loadResumable() {
    const snapshot = await kv.get<SessionSnapshot>(storageKeys.resumableSession);
    if (!snapshot) return null;

    const SIX_HOURS = 6 * 60 * 60 * 1000;
    if (Date.now() - snapshot.savedAt > SIX_HOURS) {
      await kv.remove(storageKeys.resumableSession);
      return null;
    }
    return snapshot;
  },

  async clearResumable() {
    await kv.remove(storageKeys.resumableSession);
  },

  end() {
    set({
      kind: null,
      sessionId: null,
      childId: null,
      pathId: null,
      stageNumber: 0,
      activity: null,
      attempt: 0,
      recentAnswers: [],
      isPaused: false,
      pausedAt: null,
      isSubmitting: false,
    });
    void kv.remove(storageKeys.resumableSession);
  },
}));
