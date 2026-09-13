import { apiClient } from "@/services/api/client";
import type { ClassDetail, TopicGames } from "@/types/teacher";

/**
 * /curriculum - the syllabus, as the Adventure board reads it.
 *
 * Both calls are status and play, never a way into a lesson. The class is the
 * AI Teacher and today's frozen plan decides what it teaches; a board that
 * could start a level would be a second door into a day the schedule has not
 * reached yet.
 */
export const curriculumApi = {
  /** The child's own class with its subjects and levels. */
  forChild(childId: string) {
    return apiClient.get<ClassDetail>(`/curriculum/children/${childId}/class`);
  },

  /**
   * The three games one level offers - Find it!, Find the pairs, Pop it!
   *
   * Every question, choice and picture came out of the authored syllabus, so
   * the same level offers the same games on every afternoon. Playing them
   * marks nothing, scores nothing and unlocks nothing.
   */
  games(topicId: string) {
    return apiClient.get<TopicGames>(`/curriculum/topics/${topicId}/games`);
  },
};
