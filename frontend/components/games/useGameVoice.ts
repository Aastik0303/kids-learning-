"use client";

import { useCallback, useEffect, useRef } from "react";

import { canSpeak, speakText, stopSpeech } from "@/services/speech";

/**
 * The voice a game speaks with, and the one rule about it.
 *
 * A game is played by a child who cannot read the question on it, so the
 * question is **said**. That is the same split the class makes: the words are
 * for the ear and the picture is for the eye.
 *
 * The rule is that only one thing talks at a time. Leaving a game, changing
 * round, or walking off the page stops the sentence in progress — the class
 * narrates too, and two voices over one small pair of ears is chaos. Every game
 * speaks through this hook so there is one place that is true.
 *
 * It is the same voice as everywhere else: Edge through this app's own backend,
 * with the device's own as a fallback. `speakText` owns that choice; nothing
 * here picks a voice or a language.
 */
export function useGameVoice() {
  const spoken = useRef("");

  useEffect(() => () => stopSpeech(), []);

  const say = useCallback((text: string) => {
    const line = (text ?? "").trim();
    if (!line || !canSpeak()) return;
    stopSpeech();
    spoken.current = line;
    speakText(line);
  }, []);

  const repeat = useCallback(() => {
    if (spoken.current) {
      stopSpeech();
      speakText(spoken.current);
    }
  }, []);

  const hush = useCallback(() => stopSpeech(), []);

  return { say, repeat, hush, canSpeak: canSpeak() };
}

/**
 * A tap that landed, felt as well as seen.
 *
 * A short buzz is the one bit of feedback a child gets from a tablet without
 * looking away from what they tapped. Wrapped because `vibrate` does not exist
 * on iOS and throws behind some permission policies, and a game must not fall
 * over on a device that simply cannot buzz.
 */
export function buzz(pattern: number | number[] = 18): void {
  try {
    navigator.vibrate?.(pattern);
  } catch {
    /* a device that cannot buzz is not a broken game */
  }
}
