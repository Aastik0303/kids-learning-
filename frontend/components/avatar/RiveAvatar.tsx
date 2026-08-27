"use client";

import { useEffect } from "react";
import { useRive, useStateMachineInput } from "@rive-app/react-canvas";
import { AVATAR_CONFIG, AVATAR_EFFECT_INDEX, AVATAR_STATE_INDEX } from "./avatar.config";
import type { AvatarEffect, AvatarState } from "./avatar.types";

/**
 * The animated panda, in its own module on purpose.
 *
 * `@rive-app/react-canvas` is the heaviest thing the app imports, and the
 * avatar only ever animates when `NEXT_PUBLIC_RIVE_AVATAR_SRC` points at a real
 * `.riv` file - which it does not in this project, so every page was paying to
 * download a renderer that never drew anything. `AIAvatar` loads this file
 * dynamically, and only once it knows the artwork is really there.
 */
export default function RiveAvatar({
  state,
  effect,
  isSpeaking
}: {
  state: AvatarState;
  effect: AvatarEffect | null;
  isSpeaking: boolean;
}) {
  const { rive, RiveComponent } = useRive({
    src: AVATAR_CONFIG.rive.src,
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
