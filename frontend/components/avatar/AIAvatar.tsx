"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { AVATAR_CONFIG } from "./avatar.config";
import { AvatarFallback } from "./AvatarFallback";
import type { AvatarEffect, AvatarState } from "./avatar.types";

/**
 * Loaded only when there is artwork to animate. Without this the Rive renderer
 * shipped in the first bundle of every page, including the ones a child waits
 * on, to draw nothing at all.
 */
const RiveAvatar = dynamic(() => import("./RiveAvatar"), { ssr: false });

export function AIAvatar({ state, effect, isSpeaking }: { state: AvatarState; effect: AvatarEffect | null; isSpeaking: boolean }) {
  const [canUseRive, setCanUseRive] = useState(false);
  const riveSrc = AVATAR_CONFIG.rive.src;

  useEffect(() => {
    if (!riveSrc) {
      setCanUseRive(false);
      return;
    }
    let active = true;
    fetch(riveSrc, { method: "HEAD" })
      .then((response) => {
        if (active) setCanUseRive(response.ok);
      })
      .catch(() => {
        if (active) setCanUseRive(false);
      });
    return () => {
      active = false;
    };
  }, [riveSrc]);

  if (!canUseRive) {
    return <AvatarFallback state={state} isSpeaking={isSpeaking} />;
  }

  return <RiveAvatar state={state} effect={effect} isSpeaking={isSpeaking} />;
}
