import { useMemo } from "react";

import { resolveExperienceMode } from "@/store/childStore";
import { classVisual } from "@/theme/colors";
import type { ChildProfile, ToddlerModule } from "@/types/domain";

/**
 * What to learn next.
 *
 * Deliberately deterministic and local. The project rule is that the LLM
 * never drives progression, and "what comes next" is progression — so it
 * is computed from the child's own path progress, not asked for.
 *
 * The AI still *presents* the recommendation warmly; it just does not
 * choose it.
 */

export type Recommendation = {
  pathId: string;
  stageNumber: number;
  title: string;
  /** Short line explaining why, shown above the CTA. */
  reason: string;
  isNew: boolean;
  toddlerModule: ToddlerModule;
};

/** The authored order of the core paths, mirroring the web prototype. */
const PATH_ORDER = ["numbers", "alphabets", "colours", "shapes"] as const;

const TODDLER_MODULES: readonly ToddlerModule[] = ["alphabets", "numbers", "colours", "shapes"];

export function useRecommendation(child: ChildProfile | null): Recommendation | null {
  return useMemo(() => {
    if (!child) return null;

    const isToddler = resolveExperienceMode(child) === "toddler";

    if (isToddler) {
      // Toddlers walk the modules in order, one level at a time.
      const module =
        TODDLER_MODULES.find((candidate) => !child.completed_paths.includes(candidate)) ??
        TODDLER_MODULES[0]!;
      const progress = child.path_progress[module];
      const level = progress?.current_stage ?? 1;

      return {
        pathId: module,
        stageNumber: level,
        title: `${classVisual(module).label} — level ${level}`,
        reason: level > 1 ? "Carry on where you stopped" : "Let us start here",
        isNew: level === 1 && !progress,
        toddlerModule: module,
      };
    }

    // 1. An unfinished path the child has already started.
    for (const pathId of PATH_ORDER) {
      const progress = child.path_progress[pathId];
      if (progress && !child.completed_paths.includes(pathId)) {
        return {
          pathId,
          stageNumber: progress.current_stage,
          title: `${classVisual(pathId).label} — level ${progress.current_stage}`,
          reason: "Carry on where you stopped",
          isNew: false,
          toddlerModule: "alphabets",
        };
      }
    }

    // 2. The next path never started.
    const nextPath = PATH_ORDER.find((pathId) => !child.completed_paths.includes(pathId));
    if (nextPath) {
      return {
        pathId: nextPath,
        stageNumber: 1,
        title: `${classVisual(nextPath).label} — level 1`,
        reason: "A brand new adventure",
        isNew: true,
        toddlerModule: "alphabets",
      };
    }

    // 3. Everything done — the mixed final, if it is unlocked.
    if (child.mixed_path_unlocked && !child.completed_paths.includes("mixed_final")) {
      const progress = child.path_progress["mixed_final"];
      return {
        pathId: "mixed_final",
        stageNumber: progress?.current_stage ?? 1,
        title: "Rainbow Castle — the big finish",
        reason: "You unlocked the final challenge!",
        isNew: !progress,
        toddlerModule: "alphabets",
      };
    }

    // 4. Nothing left — send them to practice instead of a dead CTA.
    const weakSkill = child.weak_skills[0];
    return {
      pathId: weakSkill ?? "numbers",
      stageNumber: 1,
      title: weakSkill ? `Practise ${weakSkill}` : "Practise what you know",
      reason: "You finished everything! Let us practise.",
      isNew: false,
      toddlerModule: "alphabets",
    };
  }, [child]);
}
