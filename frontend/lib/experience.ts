import type { ExperienceMode } from "@/types";

/**
 * Presentation rules come from the manifest, so this file holds no numbers of
 * its own beyond a last-resort fallback for the moment before the server
 * responds. `early` (Play Group, Nursery) is the stricter of the two modes, so
 * the fallback is the strict one: it is safer to be briefly too large than
 * briefly too small.
 */
export const FALLBACK_MODE: ExperienceMode = {
  mode_id: "early",
  applies_to: [],
  touch_target_px: 96,
  max_choices_per_screen: 2,
  text_density: "none",
  voice: "always",
  idle_thresholds_seconds: [12, 25, 40, 60, 80]
};

/**
 * The minimum size of a *learning* control: an answer choice, a topic tile, an
 * activity target. It deliberately does not apply to navigation or app chrome —
 * a back arrow does not need to be 96px, and forcing it there makes the chrome
 * crowd out the learning area.
 */
export function learningTargetStyle(mode: ExperienceMode) {
  return {
    minHeight: `${mode.touch_target_px}px`,
    minWidth: `${mode.touch_target_px}px`
  } as const;
}

/** `early` mode is icon and voice only: no written words for a pre-reader. */
export function showsText(mode: ExperienceMode): boolean {
  return mode.text_density !== "none";
}
