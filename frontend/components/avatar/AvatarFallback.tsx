"use client";

import { useId } from "react";
import type { AvatarState } from "./avatar.types";

/**
 * The panda, drawn.
 *
 * This used to be a stack of absolutely-positioned <span>s whose offsets were
 * written in rem against the 4.4rem avatar dock. `/ai-teacher` stands the same
 * avatar in a 14rem stage, where those fixed offsets left the ears in the
 * corners and the mouth adrift - which is what made it look like a diagram of
 * a panda rather than one. It is now a single viewBox'd SVG, so every feature
 * keeps its proportion at any size, and there is room for the things that
 * actually read as fur: shaded volume on the head, the tilted teardrop eye
 * patches, wet-looking eyes with a highlight, and a soft muzzle.
 *
 * Animation still comes from CSS on the wrapper's state classes, so the
 * reduced-motion rule at the bottom of globals.css keeps working unchanged.
 */
export function AvatarFallback({
  state,
  isSpeaking,
  holding = false
}: {
  state: AvatarState;
  isSpeaking: boolean;
  /**
   * The class's pose: the panda stands smaller and higher in the frame and
   * holds a board in front of it, and whatever is being taught is drawn on that
   * board. One picture instead of two - a teacher and, separately, a diagram -
   * which is the whole point: a three-year-old looks at one place.
   *
   * `panda-upper` is what makes it one drawing rather than two. The head, its
   * ears and every one of the face groups ride inside that one group, so the
   * pose is a single transform on it and the fourteen feelings underneath keep
   * working untouched.
   */
  holding?: boolean;
}) {
  // Two of these can be on one page (the dock and a page's own stage), and a
  // duplicated gradient id would let one steal the other's paint.
  const uid = useId().replace(/:/g, "");
  const fur = `${uid}-fur`;
  const belly = `${uid}-belly`;
  const blush = `${uid}-blush`;
  const gloss = `${uid}-gloss`;
  const screen = `${uid}-screen`;

  return (
    <div
      className={`avatar-fallback avatar-${state} ${isSpeaking ? "avatar-is-speaking" : ""} ${
        holding ? "panda-holds" : ""
      }`}
      aria-hidden="true"
    >
      <svg className="panda" viewBox="0 0 200 200" role="presentation" focusable="false">
        <defs>
          <radialGradient id={fur} cx="38%" cy="30%" r="78%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="62%" stopColor="#f9f6f2" />
            <stop offset="100%" stopColor="#e3dcd4" />
          </radialGradient>
          <radialGradient id={belly} cx="42%" cy="26%" r="80%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#e6dfd7" />
          </radialGradient>
          <radialGradient id={gloss} cx="50%" cy="34%" r="62%">
            <stop offset="0%" stopColor="#6d5a52" />
            <stop offset="100%" stopColor="#241d19" />
          </radialGradient>
          <filter id={blush} x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="4.5" />
          </filter>
        </defs>

        {/* Everything above the shoulders, in one group. Holding the board is a
            single transform on this - the head lifts and shrinks to make room
            for the board below it - and nothing inside has to know about it.
            `translate(100 50) scale(0.56) translate(-100 -94)` takes the head's
            own centre, (100, 94), to (100, 50) at 0.56 scale. Those two numbers
            are not free: the ear tops have to land inside the frame (they land
            at y 6, and `overflow: visible` would happily draw them across the
            card above), and the chin has to land far enough above the screen -
            y 83, against a screen top of 92 - to leave a band of shoulder
            showing. Without that band the panda was a head resting on a
            monitor. */}
        <g
          className="panda-upper"
          transform={holding ? "translate(100 50) scale(0.56) translate(-100 -94)" : undefined}
        >
        {/* Ears first, so the head's edge overlaps them and they read as set
            into the skull rather than stuck on. */}
        <g className="panda-ears">
          <g className="panda-ear panda-ear-left">
            <circle cx="50" cy="42" r="27" fill={`url(#${gloss})`} />
            <circle cx="50" cy="44" r="13" fill="#7d6259" opacity="0.75" />
          </g>
          <g className="panda-ear panda-ear-right">
            <circle cx="150" cy="42" r="27" fill={`url(#${gloss})`} />
            <circle cx="150" cy="44" r="13" fill="#7d6259" opacity="0.75" />
          </g>
        </g>

        {/* Body and arms, behind the head. The two arms hang at the panda's
            sides only when its paws are free; holding the board, they come
            round the front and are drawn last of all, over it. */}
        <g className="panda-body">
          {holding ? null : (
            <>
              <ellipse cx="60" cy="163" rx="17" ry="24" fill={`url(#${gloss})`} transform="rotate(18 60 163)" />
              {/* The waving arm is wrapped so its CSS animation composes with
                  the tilt rather than replacing it and snapping the arm
                  upright. */}
              <g className="panda-paw-right">
                <ellipse cx="140" cy="163" rx="17" ry="24" fill={`url(#${gloss})`} transform="rotate(-18 140 163)" />
              </g>
            </>
          )}
          <ellipse cx="100" cy="170" rx="46" ry="33" fill={`url(#${belly})`} />
          <ellipse cx="79" cy="191" rx="16" ry="11" fill={`url(#${gloss})`} />
          <ellipse cx="121" cy="191" rx="16" ry="11" fill={`url(#${gloss})`} />
        </g>

        <g className="panda-head">
          <ellipse cx="100" cy="94" rx="67" ry="59" fill={`url(#${fur})`} />

          {/* The signature patches: teardrops, tilted in towards the nose. */}
          <ellipse cx="72" cy="89" rx="19" ry="24" fill={`url(#${gloss})`} transform="rotate(-22 72 89)" />
          <ellipse cx="128" cy="89" rx="19" ry="24" fill={`url(#${gloss})`} transform="rotate(22 128 89)" />

          <ellipse className="panda-cheek" cx="54" cy="118" rx="13" ry="8" fill="#e87891" opacity="0.42" filter={`url(#${blush})`} />
          <ellipse className="panda-cheek" cx="146" cy="118" rx="13" ry="8" fill="#e87891" opacity="0.42" filter={`url(#${blush})`} />

          {/* Eyebrows. They sit on the white fur above the patches, because a
              dark brow drawn on a black eye patch is invisible - and they do
              most of the emotional work: the difference between "I am
              listening" and "oh dear" is two short strokes. All hidden until a
              feeling asks for one. */}
          <g className="panda-brows">
            <g className="panda-brow-set panda-brows-soft">
              <path d="M58 65 Q72 56 87 58" />
              <path d="M142 65 Q128 56 113 58" />
            </g>
            <g className="panda-brow-set panda-brows-up">
              <path d="M58 58 Q72 49 87 55" />
              <path d="M142 58 Q128 49 113 55" />
            </g>
            <g className="panda-brow-set panda-brows-one">
              <path d="M58 63 Q72 60 87 63" />
              <path d="M142 55 Q128 47 113 53" />
            </g>
            {/* Sorry. The inner ends climb towards the nose and the outer ends
                drop away - the one brow shape a face cannot fake, and the whole
                difference between "oh dear" and "I am thinking". */}
            <g className="panda-brow-set panda-brows-sad">
              <path d="M57 70 Q71 61 88 54" />
              <path d="M143 70 Q129 61 112 54" />
            </g>
          </g>

          <g className="panda-eyes">
            <g>
              <circle cx="76" cy="91" r="9.6" fill="#fffdfb" />
              <circle cx="76.6" cy="91.6" r="6.6" fill="#241d19" />
              <circle cx="74" cy="88.6" r="2.7" fill="#ffffff" />
              <circle cx="79" cy="94" r="1.3" fill="#ffffff" opacity="0.8" />
            </g>
            <g>
              <circle cx="124" cy="91" r="9.6" fill="#fffdfb" />
              <circle cx="123.4" cy="91.6" r="6.6" fill="#241d19" />
              <circle cx="121" cy="88.6" r="2.7" fill="#ffffff" />
              <circle cx="126" cy="94" r="1.3" fill="#ffffff" opacity="0.8" />
            </g>
          </g>

          {/* Eyes shut in a smile. White, for the same reason the brows are
              dark: this arc is drawn *on* the black patch. */}
          <g className="panda-eyes-joy">
            <path d="M64 95 Q76 82 88 95" />
            <path d="M112 95 Q124 82 136 95" />
          </g>

          {/* And eyes squeezed shut - the same two arcs the other way up. A
              crying face needs them: round open eyes with tears running out of
              them read as a leak rather than as weeping. */}
          <g className="panda-eyes-shut">
            <path d="M64 88 Q76 100 88 88" />
            <path d="M112 88 Q124 100 136 88" />
          </g>


          {/* Muzzle, so the nose sits on something instead of floating. */}
          <ellipse cx="100" cy="122" rx="27" ry="19" fill="#fffdfa" opacity="0.95" />

          <path
            d="M100 108c7.4 0 12.4 2.6 12.4 6.4 0 4.2-5.6 8.8-12.4 8.8s-12.4-4.6-12.4-8.8c0-3.8 5-6.4 12.4-6.4z"
            fill={`url(#${gloss})`}
          />
          <ellipse cx="95.4" cy="112.4" rx="3" ry="1.9" fill="#ffffff" opacity="0.42" transform="rotate(-18 95.4 112.4)" />

          <path className="panda-lip" d="M100 123v6" stroke="#241d19" strokeWidth="3" strokeLinecap="round" fill="none" />

          {/* The mouth it is wearing while it is not talking. One of these is
              showing at a time; `panda-mouth-rest` is what the talking mouth
              hides, so a new feeling can never leave two mouths on the face. */}
          <g className="panda-mouth-rest">
            <path
              className="panda-mouth panda-mouth-closed"
              d="M100 129c-3.4 6.6-11.6 6.2-14.4 1.2M100 129c3.4 6.6 11.6 6.2 14.4 1.2"
              stroke="#241d19"
              strokeWidth="3.2"
              strokeLinecap="round"
              fill="none"
            />
            <path
              className="panda-mouth panda-mouth-soft"
              d="M92 130q8 5 16 0"
              stroke="#241d19"
              strokeWidth="3"
              strokeLinecap="round"
              fill="none"
            />
            <path
              className="panda-mouth panda-mouth-frown"
              d="M89 134q11 -8 22 0"
              stroke="#241d19"
              strokeWidth="3.2"
              strokeLinecap="round"
              fill="none"
            />
            <g className="panda-mouth panda-mouth-grin">
              <path d="M81 127q19 22 38 0z" fill="#3a2723" />
              <ellipse cx="100" cy="139" rx="7.4" ry="4.6" fill="#e07f92" />
            </g>
            <ellipse className="panda-mouth panda-mouth-oh" cx="100" cy="133" rx="6.8" ry="8.4" fill="#3a2723" />
            {/* Wailing: wide at the top, tapering, with the tongue showing.
                A frown alone is disappointment; this is the mouth that goes
                with the tears. */}
            <g className="panda-mouth panda-mouth-cry">
              <path d="M85 132q15 -10 30 0q-3 17 -15 17t-15 -17z" fill="#3a2723" />
              <ellipse cx="100" cy="144" rx="6.4" ry="3.8" fill="#e07f92" />
            </g>
          </g>
          <g className="panda-mouth-open">
            <ellipse cx="100" cy="136" rx="11" ry="9.5" fill="#3a2723" />
            <ellipse cx="100" cy="140.5" rx="6.6" ry="4.6" fill="#e07f92" />
          </g>

          {/* Tears, last of everything on the head so they run *over* the fur
              and the muzzle rather than under them. The muzzle is a wide white
              ellipse and it was clipping the left drop halfway down. Each falls
              on its own timing: two drops in step read as a pair of decorations
              rather than as crying. */}
          <g className="panda-tears">
            <path
              className="panda-tear panda-tear-left"
              d="M72 101c3.2 5.4 5.2 8.2 5.2 10.8a5.2 5.2 0 0 1-10.4 0c0-2.6 2-5.4 5.2-10.8z"
              fill="#7fc8ee"
            />
            <path
              className="panda-tear panda-tear-right"
              d="M128 101c3.2 5.4 5.2 8.2 5.2 10.8a5.2 5.2 0 0 1-10.4 0c0-2.6 2-5.4 5.2-10.8z"
              fill="#7fc8ee"
            />
          </g>
        </g>
        </g>

        {/* The screen the panda is holding up, and nothing on it.

            It is drawn as a device on purpose - a dark bezel, a lit face, a
            glass sheen and a little green power light that breathes - because
            "the panda is showing you something on a screen" has to be legible
            to a child who cannot read the thing on it. A plain pale rectangle
            just looked like a gap in the picture.

            What runs on it is the lesson's own drawing, laid over this SVG by
            `TeacherStage` at exactly these coordinates, and it is a live
            animation: every turn it draws itself stroke by stroke while the
            teacher talks. Putting it inside this SVG instead would mean this
            component knowing what a lesson is, which is the one thing that has
            kept the same panda usable in the dock, on the rewards shelf and in
            the class. The paws that grip it are `PandaPaws` below, a separate
            layer again for the same reason: they have to close over the
            drawing, and the drawing is not in this SVG.

            The face is x 30..170, y 100..184. `.teacher-display` in globals.css
            is those four numbers as percentages and moves only with them. */}
        {holding ? (
          <g className="panda-board">
            <defs>
              <clipPath id={screen}>
                <rect x="30" y="100" width="140" height="84" rx="7" />
              </clipPath>
            </defs>
            {/* Shoulders, and two arms reaching round the screen to hold it.
                Both are drawn *before* the screen, so the top of each arm
                disappears behind it and the arm reads as coming from a body
                rather than being stuck on the side. The screen is narrower than
                the frame for exactly this reason: without those twenty units of
                clearance down each edge there was nowhere for an arm to be, and
                the paws floated beside the picture like two dark eggs. */}
            <ellipse cx="100" cy="116" rx="46" ry="30" fill={`url(#${gloss})`} />
            <path
              d="M70 92C48 100 30 112 27 130"
              stroke={`url(#${gloss})`}
              strokeWidth="19"
              strokeLinecap="round"
              fill="none"
            />
            <path
              d="M130 92C152 100 170 112 173 130"
              stroke={`url(#${gloss})`}
              strokeWidth="19"
              strokeLinecap="round"
              fill="none"
            />
            {/* The body of the device, and the chin the light sits on. */}
            <rect x="22" y="92" width="156" height="104" rx="13" fill="#25313f" />
            <rect x="24" y="94" width="152" height="100" rx="11" fill="#33445a" />
            {/* The lit face. Light, because the lesson draws on it in ink. */}
            <rect x="30" y="100" width="140" height="84" rx="7" fill="#f7fbff" />
            {/* Glass. One soft diagonal, clipped to the face so it cannot run
                out over the bezel. */}
            <g clipPath={`url(#${screen})`}>
              <path d="M30 172 L96 100 L126 100 L30 200z" fill="#ffffff" opacity="0.5" />
            </g>
            <rect
              x="30"
              y="100"
              width="140"
              height="84"
              rx="7"
              fill="none"
              stroke="#c3d7e4"
              strokeWidth="1.6"
            />
            <circle className="panda-screen-light" cx="100" cy="190" r="2.8" fill="#7ed09a" />
          </g>
        ) : null}
      </svg>
      <span className="avatar-sparkle avatar-sparkle-one">⭐</span>
      <span className="avatar-sparkle avatar-sparkle-two">✨</span>
    </div>
  );
}

/**
 * The two paws that close over the board, drawn on their own layer.
 *
 * They are not part of the panda's SVG because of the order things have to be
 * painted in: board, then the lesson's drawing, then the paws. A paw *behind*
 * the thing it is holding is not a panda holding a board - it is a panda
 * standing near one - and the drawing has to sit between the two.
 *
 * Same viewBox as the panda and the same coordinates, so the two SVGs line up
 * exactly however big the stage is.
 */
export function PandaPaws() {
  const uid = useId().replace(/:/g, "");
  const gloss = `${uid}-paw`;
  return (
    <svg className="panda-paws" viewBox="0 0 200 200" role="presentation" focusable="false" aria-hidden="true">
      <defs>
        <radialGradient id={gloss} cx="50%" cy="34%" r="62%">
          <stop offset="0%" stopColor="#6d5a52" />
          <stop offset="100%" stopColor="#241d19" />
        </radialGradient>
      </defs>
      {/* Each hand is a mitten with three toes down its inner edge, and it
          overlaps the screen's edge by a few units - a paw that stops short of
          the thing it is holding is a panda standing next to a screen. */}
      <g transform="rotate(12 27 140)">
        <ellipse cx="27" cy="140" rx="12.5" ry="16.5" fill={`url(#${gloss})`} />
        <circle cx="35" cy="129" r="3" fill="#7d6259" opacity="0.85" />
        <circle cx="37" cy="139" r="3.2" fill="#7d6259" opacity="0.85" />
        <circle cx="35" cy="149" r="3" fill="#7d6259" opacity="0.85" />
      </g>
      <g transform="rotate(-12 173 140)">
        <ellipse cx="173" cy="140" rx="12.5" ry="16.5" fill={`url(#${gloss})`} />
        <circle cx="165" cy="129" r="3" fill="#7d6259" opacity="0.85" />
        <circle cx="163" cy="139" r="3.2" fill="#7d6259" opacity="0.85" />
        <circle cx="165" cy="149" r="3" fill="#7d6259" opacity="0.85" />
      </g>
    </svg>
  );
}
