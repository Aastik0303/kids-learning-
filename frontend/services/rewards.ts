import { api } from "@/services/api";

export type BadgeState = {
  badge_id: string;
  title: string;
  description: string;
  earned: boolean;
  progress_hint: string | null;
};

export type RewardsSummary = {
  stars: number;
  rewards: string[];
  /** Absent from a server older than the badge shelf. Always read it with `?? []`. */
  badges?: BadgeState[];
};

/**
 * The treasure bag as the server has it.
 *
 * The Rewards screen used to read stars out of `sessionStorage`, which meant a
 * refresh, a second device or a lesson finished elsewhere showed a stale count.
 * Stars and badges are ledger truth, so they are fetched.
 */
export function getRewards(childId: string) {
  return api<RewardsSummary>(`/progress/${childId}/rewards`);
}
