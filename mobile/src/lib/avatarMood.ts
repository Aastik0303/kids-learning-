import type { AvatarState } from "@/types/domain";
import type { TeacherTurn } from "@/types/teacher";

/**
 * What the panda's face is doing during a turn of the AI Teacher.
 *
 * Ported from `frontend/components/avatar/avatar.config.ts` and kept the same
 * decision for the same reason: the class is the one screen where a child
 * cannot read anything, so the avatar's face is a channel of its own. It reacts
 * to what just happened and settles into waiting once the moment has passed - a
 * panda that stayed delighted through the next question would be grinning at a
 * child who is stuck on it.
 *
 * `speaking` is not a feeling and is not returned here. The mouth is driven
 * separately, so the panda can be pleased *and* talking, which is what it is
 * doing most of the time.
 *
 * **A wrong answer never makes it sad or cry**, and that is deliberate rather
 * than a gap in the range. It makes it kind. The two sorry faces are reserved
 * for the app's own failures, in two strengths - `sad` when the microphone
 * heard nothing and the child can simply try again, `crying` when the class
 * itself could not carry on - because a child who learns that missing a letter
 * makes the panda cry learns to stop answering.
 */
export function avatarMoodForTeacher(now: {
  speaking: boolean;
  listening: boolean;
  waiting: boolean;
  /**
   * The verdict is still fresh, whether or not anything is being said. Without
   * it a right answer's face is over before it has been seen: "Well done!" is
   * under a second of audio and a three-year-old is still looking at their own
   * finger.
   */
  reacting?: boolean;
  /** The app let the child down - not the other way round. */
  sorry: boolean;
  /** And badly: the class could not answer at all. */
  failed?: boolean;
  turn: TeacherTurn | null;
}): AvatarState {
  if (now.failed) return "crying";
  if (now.sorry) return "sad";
  if (now.listening) return "listening";

  const turn = now.turn;
  if (!turn) return now.waiting ? "thinking" : "idle";
  if (turn.day_complete) return "proud";

  // A fresh verdict outranks "thinking". The two were once the other way round,
  // so the moment a right answer was sent the panda went straight to its
  // working face and the child never saw it pleased.
  const fresh = now.speaking || Boolean(now.reacting);
  if (now.waiting && !fresh) return "thinking";

  if (fresh) {
    if (turn.topic_completed) return "proud";
    if (turn.is_correct === true) return "celebrating";
    if (turn.is_correct === false) return "encouraging";
    if (turn.is_reveal) return "encouraging";
    if (turn.is_hint) return "thinking";
    if (turn.is_retention_test) return "curious";
    return "storytelling";
  }

  // Finished talking. Now it is the child's turn, and the face says so.
  if (turn.expects === "tap" || turn.expects === "voice") return "curious";
  return "idle";
}
