import { useState, type ReactNode } from "react";
import { View, type LayoutChangeEvent } from "react-native";

import { PandaAvatar, PandaPaws } from "@/components/avatar/PandaAvatar";
import type { AvatarState } from "@/types/domain";

/**
 * The teacher, holding the thing it is teaching.
 *
 * The class used to be two pictures stacked - a panda, and under it a drawing
 * of whatever the card was about - and two pictures is one too many for a
 * three-year-old, who looks at whichever moved last. So the panda stands behind
 * a board and holds it up, and the lesson's drawing appears **on the board**.
 * The teacher and the lesson are one thing to look at, and the face doing the
 * reacting is directly above the answer it is reacting to.
 *
 * Three layers, and the order is the whole trick:
 *
 *   1. the panda in its `holding` pose - head lifted and smaller, arms round
 *      the front, an empty board in its paws;
 *   2. the drawing, laid over the board's face, because the drawing is its own
 *      animated component and does not belong inside somebody else's SVG;
 *   3. the paws, over the top, so they close over the board *and* the drawing
 *      on it.
 *
 * Layers 1 and 3 are two SVGs with the same viewBox, and layer 2 is placed by
 * percentages taken from the same coordinates - the board's lit face is the
 * `x 30, y 100, 140 x 84` rect in `PandaAvatar`, which out of a 200x200 viewBox
 * is 15% / 50% / 70% / 42%. Those four numbers and that rect move together.
 *
 * **The stage measures itself into a square**, and that is load-bearing rather
 * than tidiness: an SVG centres itself inside whatever box it is given, while
 * the percentages above are of *the box*. Hand this a portrait box and the
 * panda letterboxes itself in the middle of it while the drawing slides off the
 * paws that are supposed to be holding it. So the square is taken as the
 * smaller of the two sides and centred, and the three layers are laid out
 * inside that.
 */
export function TeacherStage({
  state,
  isSpeaking,
  children,
}: {
  state: AvatarState;
  isSpeaking: boolean;
  /**
   * What is drawn on the board. Nothing is a perfectly good answer: an
   * explaining card with no picture leaves the panda holding a blank board,
   * which is exactly what a teacher between things is doing.
   */
  children?: ReactNode;
}) {
  const [side, setSide] = useState(0);

  const measure = (event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    const next = Math.floor(Math.min(width, height));
    if (next > 0 && next !== side) setSide(next);
  };

  return (
    <View
      style={{ flex: 1, width: "100%", alignItems: "center", justifyContent: "center" }}
      onLayout={measure}
      testID="teacher-stage"
    >
      {side > 0 ? (
        <View style={{ width: side, height: side }}>
          <PandaAvatar state={state} isSpeaking={isSpeaking} holding />

          {/* The board's lit face, and whatever the lesson is drawing on it.
              `overflow: hidden` is the last word on the edges: a letter drawn
              at a size chosen for a card used to hang a third of its height
              below the board and across the question underneath it. */}
          <View
            style={{
              position: "absolute",
              left: side * 0.15,
              top: side * 0.5,
              width: side * 0.7,
              height: side * 0.42,
              overflow: "hidden",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {/* Inset a little, so a drawing that fills its own box does not run
                into the board's edge. */}
            <View style={{ position: "absolute", left: "4%", top: "4%", right: "4%", bottom: "4%" }}>
              {children}
            </View>
          </View>

          <PandaPaws />
        </View>
      ) : null}
    </View>
  );
}
