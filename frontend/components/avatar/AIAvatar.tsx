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

export function AIAvatar({
  state,
  effect,
  isSpeaking,
  holding = false
}: {
  state: AvatarState;
  effect: AvatarEffect | null;
  isSpeaking: boolean;
  /**
   * Stand the panda up behind a board and let it hold the board rather than its
   * own paws. The class uses this pose: the teacher and the thing being taught
   * are one picture, so a child looks at one place on the screen instead of
   * two. Rive artwork has no such pose, so this only reaches the drawn panda.
   */
  holding?: boolean;
}) {
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
    return <AvatarFallback state={state} isSpeaking={isSpeaking} holding={holding} />;
  }

  return <RiveAvatar state={state} effect={effect} isSpeaking={isSpeaking} />;
}
