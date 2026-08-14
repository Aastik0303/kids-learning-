import { create } from "zustand";

import { childApi } from "@/services/api/childApi";
import { kv, storageKeys } from "@/services/storage/kv";
import { track } from "@/services/analytics/analytics";
import type { ChildProfile, LearningMode } from "@/types/domain";

/**
 * Which adaptive UI mode the child experience runs in (spec section 4).
 * One app, two modes — never two apps.
 */
export type ExperienceMode = "toddler" | "earlyLearner";

/**
 * Age is the primary signal, with mastery as a secondary one: a 3-year-old
 * who has completed nothing still benefits from toddler pacing, while the
 * backend's own `learning_mode` always wins if it has been set explicitly.
 */
/**
 * Age-only mode rule, for the setup screen's preview where no profile
 * exists yet. Mirrors the backend threshold in `toddler_service.py`.
 */
export function modeForAge(age: number): ExperienceMode {
  return age < 3 ? "toddler" : "earlyLearner";
}

export function resolveExperienceMode(child: ChildProfile | null): ExperienceMode {
  if (!child) return "earlyLearner";

  if (child.learning_mode === "toddler") return "toddler";
  if (child.learning_mode === "standard") return "earlyLearner";

  const age = child.age ?? parseInt(child.age_group, 10);
  if (Number.isFinite(age) && age < 3) return "toddler";

  // No age at all and no progress yet: start gentle.
  const hasProgress = child.stars > 0 || child.completed_paths.length > 0;
  if (!Number.isFinite(age) && !hasProgress) return "toddler";

  return "earlyLearner";
}

type ChildState = {
  children: ChildProfile[];
  activeChild: ChildProfile | null;
  isLoading: boolean;
  error: string | null;

  loadChildren: (sessionToken: string) => Promise<void>;
  selectChild: (child: ChildProfile) => Promise<void>;
  createChild: (input: {
    sessionToken: string;
    name: string;
    age: number;
    preferredLanguage: string;
  }) => Promise<ChildProfile | null>;
  updateChild: (input: {
    sessionToken: string;
    age?: number;
    name?: string;
    preferredLanguage?: string;
  }) => Promise<void>;
  /** Applies a fresh profile returned by a learning/practice response. */
  syncProfile: (child: ChildProfile) => void;
  refresh: () => Promise<void>;
  restoreCached: () => Promise<void>;
  clear: () => void;
};

/** Backend expects a coarse age band alongside the exact age. */
export function ageGroupFor(age: number): string {
  if (age < 3) return "1-2";
  if (age < 4) return "3-4";
  if (age < 6) return "4-5";
  return "6-8";
}

export const useChildStore = create<ChildState>((set, get) => ({
  children: [],
  activeChild: null,
  isLoading: false,
  error: null,

  async loadChildren(sessionToken) {
    set({ isLoading: true, error: null });
    try {
      const children = await childApi.list(sessionToken);
      set({ children, isLoading: false });

      // Re-select the previously chosen child if they still exist.
      const storedId = await kv.get<string>(storageKeys.selectedChildId);
      const previous = children.find((child) => child.child_id === storedId);
      if (previous) {
        set({ activeChild: previous });
      } else if (children.length === 1 && children[0]) {
        set({ activeChild: children[0] });
      }
    } catch {
      set({ isLoading: false, error: "We could not load profiles right now." });
    }
  },

  async selectChild(child) {
    set({ activeChild: child });
    await Promise.all([
      kv.set(storageKeys.selectedChildId, child.child_id),
      kv.set(storageKeys.cachedChild, child),
    ]);
  },

  async createChild({ sessionToken, name, age, preferredLanguage }) {
    set({ isLoading: true, error: null });
    try {
      const child = await childApi.create({
        sessionToken,
        name,
        age,
        ageGroup: ageGroupFor(age),
        preferredLanguage,
      });
      set((state) => ({
        children: [...state.children, child],
        activeChild: child,
        isLoading: false,
      }));
      await get().selectChild(child);
      track("child_profile_created", {
        age_group: child.age_group,
        mode: resolveExperienceMode(child),
      });
      return child;
    } catch {
      set({ isLoading: false, error: "We could not create that profile right now." });
      return null;
    }
  },

  async updateChild({ sessionToken, age, name, preferredLanguage }) {
    const active = get().activeChild;
    if (!active) return;

    try {
      const updated = await childApi.update(active.child_id, {
        sessionToken,
        ...(age === undefined ? {} : { age, ageGroup: ageGroupFor(age) }),
        ...(name === undefined ? {} : { name }),
        ...(preferredLanguage === undefined ? {} : { preferredLanguage }),
      });
      get().syncProfile(updated);
    } catch {
      set({ error: "We could not save that change." });
    }
  },

  syncProfile(child) {
    set((state) => ({
      activeChild: state.activeChild?.child_id === child.child_id ? child : state.activeChild,
      children: state.children.map((existing) =>
        existing.child_id === child.child_id ? child : existing,
      ),
    }));
    void kv.set(storageKeys.cachedChild, child);
  },

  /** Pull the latest stars/progress after a lesson without a full reload. */
  async refresh() {
    const active = get().activeChild;
    if (!active) return;
    try {
      const child = await childApi.get(active.child_id);
      get().syncProfile(child);
    } catch {
      // Keep showing the last known profile; this is a background refresh.
    }
  },

  /** Offline cold start: show the last known child rather than nothing. */
  async restoreCached() {
    const cached = await kv.get<ChildProfile>(storageKeys.cachedChild);
    if (cached && !get().activeChild) {
      set({ activeChild: cached, children: [cached] });
    }
  },

  clear() {
    set({ children: [], activeChild: null, error: null });
  },
}));
