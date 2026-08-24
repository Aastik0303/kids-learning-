import { api } from "@/services/api";
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
  return api<TodayPlan>(`/plans/${childId}/today`);
}

/** The subject a plan item belongs to, read off the skill id it carries. */
export function subjectOf(skillId: string): string | null {
  const [subjectId] = skillId.split(":");
  return subjectId && subjectId !== skillId ? subjectId : null;
}
