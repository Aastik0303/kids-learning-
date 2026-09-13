"use client";

import { AIAvatar } from "./AIAvatar";
import { PandaPaws } from "./AvatarFallback";
import type { AvatarState } from "./avatar.types";

/**
 * The teacher, holding the thing it is teaching.
 *
 * The class used to be two pictures stacked: a panda, and under it a drawing of
 * whatever the card was about. Two pictures is one too many for a three-year-old
 * - they look at one, and it is whichever moved last. So the panda stands
 * behind a board and holds it up, and the lesson's drawing appears **on the
 * board**. The teacher and the lesson are one thing to look at, and the face
 * doing the reacting is right above the answer it is reacting to.
 *
 * It is three layers, and the order is the whole trick:
 *
 * 1. the panda in its `holding` pose - head lifted and smaller, arms round the
 *    front, an empty board in its paws;
 * 2. the drawing, laid over the board's face in HTML, because the drawing is a
 *    React component with its own animation and does not belong inside somebody
 *    else's SVG;
 * 3. `PandaPaws`, over the top, so the paws close over the board *and* the
 *    drawing on it. A paw behind the thing it is holding is a panda standing
 *    near a board.
 *
 * Layers 1 and 3 are two SVGs with the same `viewBox`, and layer 2 is placed by
 * percentages taken from the same coordinates, so all three line up at any
 * size. The numbers in `.teacher-display` are the board's lit face - the
 * `x 30, y 100, 140 x 84` rect in `AvatarFallback`, out of a 200x200 viewBox,
 * which is 15% / 50% / 70% / 42% - and the two have to be changed together.
 *
 * They line up only while this box is **square**, because the panda centres
 * itself inside whatever box it is given and the percentages above are of the
 * box rather than of the panda. Keeping it square is `.class-stage`'s job and
 * it is the reason that rule asks for `min(100cqw, 100cqh)` rather than for a
 * height with a ratio: see the comment there.
 */
export function TeacherStage({
  state,
  isSpeaking,
  children
}: {
  state: AvatarState;
  isSpeaking: boolean;
  /** What is drawn on the board. Nothing is a perfectly good answer: an
   *  explaining card with no picture leaves the panda holding a blank slate,
   *  which is exactly what a teacher between things is doing. */
  children?: React.ReactNode;
}) {
  return (
    <div className="teacher-stage" data-testid="teacher-stage">
      <div className="teacher-panda">
        <AIAvatar state={state} effect={null} isSpeaking={isSpeaking} holding />
      </div>
      <div className="teacher-display">{children}</div>
      <PandaPaws />
    </div>
  );
}
