import { useQuery } from "@tanstack/react-query";

import { planApi } from "@/services/api/planApi";
import { queryClient } from "@/services/queryClient";
import { useChildStore } from "@/store/childStore";
import type { PlanItem, RetentionTestItem, TodayPlan } from "@/types/teacher";

/**
 * Today's frozen plan, read once and shared by everything that shows it.
 *
 * The plan is the day's work and the class is built out of it: one stage per
 * planned item, in order, and when the last one is through the day is shut
 * until tomorrow. That makes it the shape of the whole sitting rather than a
 * decoration, which is why the strip that draws it is on every screen.
 *
 * It is frozen server-side per child per day, so this is a read: asking twice
 * does not produce two different days. A consequence worth knowing when
 * changing how a day is built - the change is invisible until tomorrow unless
 * today's rows are deleted and allowed to re-freeze.
 */
export function useTodayPlan() {
  const child = useChildStore((state) => state.activeChild);
  const childId = child?.child_id ?? null;

  const query = useQuery({
    queryKey: ["plan", "today", childId],
    queryFn: () => planApi.today(childId as string),
    enabled: Boolean(childId),
    // A plan that has just been moved by finishing a stage is not stale-by-time,
    // it is stale-by-event; `announcePlanChanged` is what says so.
    staleTime: 5 * 60 * 1000,
  });

  const plan: TodayPlan | null = query.data ?? null;
  const items: PlanItem[] = plan?.items ?? [];
  const retentionTests: RetentionTestItem[] = plan?.retention_tests ?? [];

  return {
    plan,
    items,
    retentionTests,
    /** Every level of the day is through. What comes next is tomorrow's plan. */
    complete: Boolean(plan?.complete),
    isLoading: query.isLoading,
    plannedTopicIds: new Set(items.map((item) => item.topic_id)),
    retentionTopicIds: new Set(retentionTests.map((test) => test.topic_id)),
  };
}

/**
 * The day has moved: re-read it.
 *
 * Called when a stage finishes, because the level that was current a moment ago
 * is done now and the schedule strip on every screen is drawing the old one.
 */
export function announcePlanChanged() {
  void queryClient.invalidateQueries({ queryKey: ["plan"] });
  void queryClient.invalidateQueries({ queryKey: ["curriculum"] });
}
