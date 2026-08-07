"use client";

import type { AvatarState } from "./avatar.types";

export function AvatarFallback({ state, isSpeaking }: { state: AvatarState; isSpeaking: boolean }) {
  return (
    <div className={`avatar-fallback avatar-${state} ${isSpeaking ? "avatar-is-speaking" : ""}`} aria-hidden="true">
      <span className="avatar-ear avatar-ear-left" />
      <span className="avatar-ear avatar-ear-right" />
      <span className="avatar-face">
        <span className="avatar-eye avatar-eye-left" />
        <span className="avatar-eye avatar-eye-right" />
        <span className="avatar-nose" />
        <span className="avatar-mouth" />
        <span className="avatar-cheek avatar-cheek-left" />
        <span className="avatar-cheek avatar-cheek-right" />
      </span>
      <span className="avatar-paw avatar-paw-left" />
      <span className="avatar-paw avatar-paw-right" />
      <span className="avatar-sparkle avatar-sparkle-one">⭐</span>
      <span className="avatar-sparkle avatar-sparkle-two">✨</span>
    </div>
  );
}
