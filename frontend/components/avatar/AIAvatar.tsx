"use client";

import { useEffect, useState } from "react";
import { useRive, useStateMachineInput } from "@rive-app/react-canvas";
import { AVATAR_CONFIG, AVATAR_EFFECT_INDEX, AVATAR_STATE_INDEX } from "./avatar.config";
import { AvatarFallback } from "./AvatarFallback";
import type { AvatarEffect, AvatarState } from "./avatar.types";

function RiveAvatar({ state, effect, isSpeaking }: { state: AvatarState; effect: AvatarEffect | null; isSpeaking: boolean }) {
  const src = AVATAR_CONFIG.rive.src;
  const { rive, RiveComponent } = useRive({
    src,
    stateMachines: AVATAR_CONFIG.rive.stateMachine,
    autoplay: true
  });
  const stateInput = useStateMachineInput(rive, AVATAR_CONFIG.rive.stateMachine, AVATAR_CONFIG.rive.stateInput);
  const speakingInput = useStateMachineInput(rive, AVATAR_CONFIG.rive.stateMachine, AVATAR_CONFIG.rive.speakingInput);
  const effectInput = useStateMachineInput(rive, AVATAR_CONFIG.rive.stateMachine, AVATAR_CONFIG.rive.effectInput);

  useEffect(() => {
    if (stateInput) stateInput.value = AVATAR_STATE_INDEX[state];
  }, [state, stateInput]);

  useEffect(() => {
    if (speakingInput) speakingInput.value = isSpeaking;
  }, [isSpeaking, speakingInput]);

  useEffect(() => {
    if (effectInput) effectInput.value = AVATAR_EFFECT_INDEX[effect ?? "none"];
  }, [effect, effectInput]);

  return <RiveComponent className="h-full w-full" aria-label={`${AVATAR_CONFIG.name} learning avatar`} />;
}

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
