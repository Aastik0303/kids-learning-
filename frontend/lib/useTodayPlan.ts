"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getTodayPlan } from "@/services/plan";
import type { ChildProfile, TodayPlan } from "@/types";

/** Fired by any screen that finishes a lesson, so the schedule redraws at once. */
export const PLAN_CHANGED_EVENT = "saksham-plan-changed";

export function announcePlanChanged() {
  if (typeof window === "undefined") return;
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

  /** The item the day is pointing at, or null when the day is done. */
  const current = useMemo(() => (plan?.items ?? []).find((item) => item.current) ?? null, [plan]);

  return {
    plan,
    plannedTopicIds,
    current,
    /** True only once the answer is known, so nothing is greyed out on a guess. */
    loaded,
    complete: Boolean(plan?.complete),
    /** The server's call, not the client's: only Play Group and Nursery. */
    autopilot: Boolean(plan?.autopilot),
    refresh: load
  };
}
