"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { AVATAR_CONFIG, tidyAvatarMessage } from "./avatar.config";
import type { AvatarContextValue, AvatarEffect, AvatarPayload, AvatarState } from "./avatar.types";
import {
  DEFAULT_VOICE_PROVIDER,
  getVoiceProvider,
  setVoiceProvider as saveVoiceProvider,
  speakText,
  speakTextAsync,
  stopSpeech,
  type VoiceProvider
} from "@/services/speech";

const AvatarContext = createContext<AvatarContextValue | null>(null);

export function AvatarProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AvatarState>(AVATAR_CONFIG.defaults.state);
  const [message, setMessage] = useState(AVATAR_CONFIG.defaults.message);
  const [effect, setEffect] = useState<AvatarEffect | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [muted, setMuted] = useState(false);
  // Starts on the server's free neural voice, not the machine's robot. Read
  // from storage after mount, never during render: localStorage does not exist
  // on the server, and disagreeing about it makes React throw the tree away.
  const [voiceProvider, setVoiceProvider] = useState<VoiceProvider>(DEFAULT_VOICE_PROVIDER);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messageRef = useRef(message);
  const mutedRef = useRef(muted);

  useEffect(() => {
    messageRef.current = message;
  }, [message]);

  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);

  useEffect(() => {
    setVoiceProvider(getVoiceProvider());
  }, []);

  const clearResetTimer = useCallback(() => {
    if (resetTimer.current) {
      clearTimeout(resetTimer.current);
      resetTimer.current = null;
    }
  }, []);

  const resetAvatar = useCallback(() => {
    clearResetTimer();
    setState(AVATAR_CONFIG.defaults.state);
    setEffect(null);
    setMessage(AVATAR_CONFIG.defaults.message);
  }, [clearResetTimer]);

  const stopSpeaking = useCallback(() => {
    stopSpeech();
    setIsSpeaking(false);
  }, []);

  const speakMessage = useCallback((nextMessage?: string) => {
    if (mutedRef.current) return;
    const text = tidyAvatarMessage(nextMessage ?? messageRef.current);
    setIsSpeaking(true);
    setState("speaking");
    const started = speakText(text, () => {
      setIsSpeaking(false);
      setState((current) => (current === "speaking" ? "idle" : current));
    });
    if (!started) setIsSpeaking(false);
  }, []);

  const speakMessageAsync = useCallback(
    async (nextMessage?: string) => {
      if (mutedRef.current) return;
      const text = tidyAvatarMessage(nextMessage ?? messageRef.current);
      setIsSpeaking(true);
      setState("speaking");
      await speakTextAsync(text);
      setIsSpeaking(false);
      setState((current) => (current === "speaking" ? "idle" : current));
    },
    []
  );

  const setAvatar = useCallback(
    (payload: AvatarPayload) => {
      clearResetTimer();
      const nextMessage = tidyAvatarMessage(payload.message);
      setState(payload.state);
      setMessage(nextMessage);
      setEffect(payload.animationEffect ?? null);
      if (payload.speak) speakMessage(nextMessage);
      const duration = payload.durationMs === null ? null : payload.durationMs ?? AVATAR_CONFIG.defaults.durationMs;
      if (duration) {
        resetTimer.current = setTimeout(() => {
          setState("idle");
          setEffect(null);
        }, duration);
      }
    },
    [clearResetTimer, speakMessage]
  );

  const toggleMute = useCallback(() => {
    setMuted((current) => {
      const next = !current;
      if (next) stopSpeech();
      return next;
    });
    setIsSpeaking(false);
  }, []);

  /**
   * Cycle the voice: Edge (free, default) → ElevenLabs (paid) → the browser's
   * own → back to Edge.
   *
   * ElevenLabs stays in the ring even though the client cannot tell whether a
   * key is configured: the server answers that question by falling back to the
   * Edge voice, so choosing it can never leave a child in silence.
   */
  const toggleVoiceProvider = useCallback(() => {
    stopSpeech();
    setIsSpeaking(false);
    setVoiceProvider((current) => {
      const order: VoiceProvider[] = ["edge", "elevenlabs", "browser"];
      const next = order[(order.indexOf(current) + 1) % order.length];
      saveVoiceProvider(next);
      return next;
    });
  }, []);

  useEffect(() => () => clearResetTimer(), [clearResetTimer]);

  const value = useMemo(
    () => ({ state, message, effect, isSpeaking, muted, voiceProvider, setAvatar, resetAvatar, speakMessage, speakMessageAsync, stopSpeaking, toggleMute, toggleVoiceProvider }),
    [effect, isSpeaking, message, muted, resetAvatar, setAvatar, speakMessage, speakMessageAsync, state, stopSpeaking, toggleMute, toggleVoiceProvider, voiceProvider]
  );

  return <AvatarContext.Provider value={value}>{children}</AvatarContext.Provider>;
}

export function useAvatar() {
  const context = useContext(AvatarContext);
  if (!context) {
    throw new Error("useAvatar must be used inside AvatarProvider");
  }
  return context;
}
