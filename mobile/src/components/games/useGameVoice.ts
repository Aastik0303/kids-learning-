import { useCallback, useEffect, useRef } from "react";

import { voiceController } from "@/features/voice/VoiceController";

/**
 * The voice a game speaks with, and the one rule about it.
 *
 * A game is played by a child who cannot read the question on it, so the
 * question is **said**. That is the same split the class makes: the words are
 * for the ear and the picture is for the eye.
 *
 * The rule is that only one thing talks at a time. Leaving a game, changing
 * round, or walking off the screen stops the sentence in progress - the class
 * narrates too, and two voices over one small pair of ears is chaos. Every game
 * speaks through this hook, so there is one place that is true.
 *
 * It is the same voice as everywhere else: whatever `voiceController` is
 * configured with. Nothing here picks a voice or a language.
 */
export function useGameVoice() {
  const spoken = useRef("");

  useEffect(() => {
    return () => {
      void voiceController.stopSpeaking();
    };
  }, []);

  const say = useCallback((text: string) => {
    const line = (text ?? "").trim();
    if (!line) return;
    spoken.current = line;
    void voiceController.speak(line);
  }, []);

  const repeat = useCallback(() => {
    if (spoken.current) void voiceController.speak(spoken.current);
  }, []);

  const hush = useCallback(() => {
    void voiceController.stopSpeaking();
  }, []);

  return { say, repeat, hush };
}
