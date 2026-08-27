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
export function AvatarFallback({ state, isSpeaking }: { state: AvatarState; isSpeaking: boolean }) {
  // Two of these can be on one page (the dock and a page's own stage), and a
  // duplicated gradient id would let one steal the other's paint.
  const uid = useId().replace(/:/g, "");
  const fur = `${uid}-fur`;
  const belly = `${uid}-belly`;
  const blush = `${uid}-blush`;
  const gloss = `${uid}-gloss`;

  return (
    <div className={`avatar-fallback avatar-${state} ${isSpeaking ? "avatar-is-speaking" : ""}`} aria-hidden="true">
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

        {/* Body and arms, behind the head. */}
        <g className="panda-body">
          <ellipse cx="60" cy="163" rx="17" ry="24" fill={`url(#${gloss})`} transform="rotate(18 60 163)" />
          {/* The waving arm is wrapped so its CSS animation composes with the
              tilt rather than replacing it and snapping the arm upright. */}
          <g className="panda-paw-right">
            <ellipse cx="140" cy="163" rx="17" ry="24" fill={`url(#${gloss})`} transform="rotate(-18 140 163)" />
          </g>
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

          {/* Muzzle, so the nose sits on something instead of floating. */}
          <ellipse cx="100" cy="122" rx="27" ry="19" fill="#fffdfa" opacity="0.95" />

          <path
            d="M100 108c7.4 0 12.4 2.6 12.4 6.4 0 4.2-5.6 8.8-12.4 8.8s-12.4-4.6-12.4-8.8c0-3.8 5-6.4 12.4-6.4z"
            fill={`url(#${gloss})`}
          />
          <ellipse cx="95.4" cy="112.4" rx="3" ry="1.9" fill="#ffffff" opacity="0.42" transform="rotate(-18 95.4 112.4)" />

          <path className="panda-lip" d="M100 123v6" stroke="#241d19" strokeWidth="3" strokeLinecap="round" fill="none" />
          <path
            className="panda-mouth-closed"
            d="M100 129c-3.4 6.6-11.6 6.2-14.4 1.2M100 129c3.4 6.6 11.6 6.2 14.4 1.2"
            stroke="#241d19"
            strokeWidth="3.2"
            strokeLinecap="round"
            fill="none"
          />
          <g className="panda-mouth-open">
            <ellipse cx="100" cy="136" rx="11" ry="9.5" fill="#3a2723" />
            <ellipse cx="100" cy="140.5" rx="6.6" ry="4.6" fill="#e07f92" />
          </g>
        </g>
      </svg>
      <span className="avatar-sparkle avatar-sparkle-one">⭐</span>
      <span className="avatar-sparkle avatar-sparkle-two">✨</span>
    </div>
  );
}
