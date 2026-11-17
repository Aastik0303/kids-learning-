import { apiClient } from "@/services/api/client";
import { env } from "@/config/env";
import type { TeacherTurn } from "@/types/teacher";

/**
 * /playground/teacher - the AI Teacher, which is the class.
 *
 * The path still says `playground` because that is where this started on the
 * server; nothing about it is a sandbox. A stage is one item of today's frozen
 * plan, five questions long, and finishing one marks the level done, pays the
 * manifest's stars and unlocks the next on the Adventure map. When the last
 * stage of the day is through the class will not reopen until tomorrow, and
 * that lock is the server's - a reload lands straight back on it.
 *
 * Three calls, and only one of them moves anything. There is no "start topic",
 * no "check answer" and no "next": naming a topic would be the client choosing
 * what the schedule has already chosen, and marking an answer here would put a
 * model upstream of a star.
 *
 * A turn is written by the big model and can take several seconds, so these
 * carry the teacher budget rather than the CRUD one; a lesson that times out at
 * six seconds is a class that will not start on a slow connection. The budget
 * outlasts the server's own wait on the model, because an answer the client
 * gave up on has still been marked.
 */
export const teacherApi = {
  /** Start or resume today's class, on whatever the frozen plan points at. */
  open(childId: string) {
    return apiClient.post<TeacherTurn>(`/playground/teacher/${childId}/open`, {}, {
      timeoutMs: env.teacherTimeoutMs,
      // Start-or-resume, so asking twice is safe - unlike `answer`, which
      // would mark the same answer against the next question.
      retries: 1,
    });
  },

  /** What the child said. Marked on the server, in Python, from the author's key. */
  answer(sessionId: string, answer: string) {
    return apiClient.post<TeacherTurn>(
      `/playground/teacher/sessions/${sessionId}/answer`,
      { answer },
      { timeoutMs: env.teacherTimeoutMs },
    );
  },

  /**
   * Something the child asked of their own accord.
   *
   * Not an answer: the lesson does not move, nothing is marked, and the
   * question the teacher had already asked is still waiting afterwards.
   */
  ask(sessionId: string, question: string) {
    return apiClient.post<TeacherTurn>(
      `/playground/teacher/sessions/${sessionId}/ask`,
      { question },
      { timeoutMs: env.teacherTimeoutMs },
    );
  },

  /** The same sitting again, with nothing moved. */
  read(sessionId: string) {
    return apiClient.get<TeacherTurn>(`/playground/teacher/sessions/${sessionId}`);
  },
};
