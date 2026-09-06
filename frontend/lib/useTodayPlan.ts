"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { forgetTodayPlan, getTodayPlan } from "@/services/plan";
import type { ChildProfile, TodayPlan } from "@/types";

/** Fired by any screen that finishes a lesson, so the schedule redraws at once. */
export const PLAN_CHANGED_EVENT = "saksham-plan-changed";

export function announcePlanChanged() {
  if (typeof window === "undefined") return;
  // Drop the shared read first: the listeners fire synchronously, and a
  // listener that re-read the plan from the cache would redraw the same day it
  // was already showing.
  forgetTodayPlan();
  window.dispatchEvent(new Event(PLAN_CHANGED_EVENT));
}

/**
 * Today's plan, for every screen that has to obey it.
 *
 * The plan is the day's work: the schedule strip renders it, the topic map greys
 * out everything it does not hold, and the server refuses anything else. All
 * three read it from here so they cannot disagree with each other.
 *
 * It is re-read when a lesson finishes and when the tab is focused again -
 * a tab left open overnight would otherwise still be showing yesterday.
 */
export function useTodayPlan(child: ChildProfile | null) {
  const [plan, setPlan] = useState<TodayPlan | null>(null);
  const [loaded, setLoaded] = useState(false);
  const childId = child?.child_id ?? null;

  const load = useCallback(() => {
    if (!childId) {
      setPlan(null);
      setLoaded(true);
      return;
    }
    getTodayPlan(childId)
      .then(setPlan)
      // The schedule is not worth breaking a screen over: a home page that
      // cannot reach it still opens the adventure.
      .catch(() => setPlan(null))
      .finally(() => setLoaded(true));
  }, [childId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const refresh = () => load();
    window.addEventListener(PLAN_CHANGED_EVENT, refresh);
    window.addEventListener("focus", refresh);
    return () => {
      window.removeEventListener(PLAN_CHANGED_EVENT, refresh);
      window.removeEventListener("focus", refresh);
    };
  }, [load]);

  const plannedTopicIds = useMemo(
    () => new Set((plan?.items ?? []).map((item) => item.topic_id)),
    [plan]
  );

  /**
   * The check-ins the schedule owes today, and the topics they are about.
   *
   * Kept apart from `plannedTopicIds` on purpose. That set is what decides
   * whether a level may be *taught* today, and a due check-in is not permission
   * to teach anything - it is a question about something already learned. Were
   * the two merged, a level whose check-in came due would stop being greyed out
   * on the map and start looking like today's lesson.
   */
  const retentionTests = useMemo(() => plan?.retention_tests ?? [], [plan]);
  const retentionTopicIds = useMemo(
    () => new Set(retentionTests.map((test) => test.topic_id)),
    [retentionTests]
  );

  /** The item the day is pointing at, or null when the day is done. */
  const current = useMemo(() => (plan?.items ?? []).find((item) => item.current) ?? null, [plan]);

  return {
    plan,
    plannedTopicIds,
    retentionTests,
    retentionTopicIds,
    current,
    /** True only once the answer is known, so nothing is greyed out on a guess. */
    loaded,
    complete: Boolean(plan?.complete),
    /** The server's call, not the client's: only Play Group and Nursery. */
    autopilot: Boolean(plan?.autopilot),
    refresh: load
  };
}
