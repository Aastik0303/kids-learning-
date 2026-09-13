import { apiClient } from "@/services/api/client";
import type { TodayPlan } from "@/types/teacher";

/**
 * /plans - today's frozen plan for one child.
 *
 * The plan is frozen server-side for the day, so this is a read: asking twice
 * does not produce two different days. It is the shape of the whole sitting -
 * the class teaches one stage per item, in order - and it is also what the
 * schedule strip draws on every screen.
 */
export const planApi = {
  today(childId: string) {
    return apiClient.get<TodayPlan>(`/plans/${childId}/today`);
  },
};
