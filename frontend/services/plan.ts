import { api } from "@/services/api";
import { invalidate, shared } from "@/services/cache";
import type { TodayPlan } from "@/types";

/**
 * Today's plan for one child.
 *
 * The plan is frozen server-side for the day, so this is a read: calling it
 * twice does not produce two different days. The background planner has usually
 * written it before the child ever opens the app; if it has not, this read is
 * what starts the day.
 */
export function getTodayPlan(childId: string) {
  // The schedule strip, the auto-open gate and the home block all ask for this
  // on the same render. They share one read; `forgetTodayPlan` is what makes a
  // finished lesson show up rather than a timer.
  return shared(`plans:today:${childId}`, () => api<TodayPlan>(`/plans/${childId}/today`));
}

/** Called when a lesson finishes: the day has moved, so re-read it. */
export function forgetTodayPlan() {
  invalidate("plans:");
}

/** The subject a plan item belongs to, read off the skill id it carries. */
export function subjectOf(skillId: string): string | null {
  const [subjectId] = skillId.split(":");
  return subjectId && subjectId !== skillId ? subjectId : null;
}
