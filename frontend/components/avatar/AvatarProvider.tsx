"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { AVATAR_CONFIG, tidyAvatarMessage } from "./avatar.config";
import type { AvatarContextValue, AvatarEffect, AvatarPayload, AvatarState } from "./avatar.types";
import { speakText, speakTextAsync, stopSpeech } from "@/services/speech";

const AvatarContext = createContext<AvatarContextValue | null>(null);

export function AvatarProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AvatarState>(AVATAR_CONFIG.defaults.state);
  const [message, setMessage] = useState(AVATAR_CONFIG.defaults.message);
  const [effect, setEffect] = useState<AvatarEffect | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [muted, setMuted] = useState(false);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messageRef = useRef(message);
  const mutedRef = useRef(muted);

  useEffect(() => {
    messageRef.current = message;
  }, [message]);

  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);

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

  useEffect(() => () => clearResetTimer(), [clearResetTimer]);

  const value = useMemo(
    () => ({ state, message, effect, isSpeaking, muted, setAvatar, resetAvatar, speakMessage, speakMessageAsync, stopSpeaking, toggleMute }),
    [effect, isSpeaking, message, muted, resetAvatar, setAvatar, speakMessage, speakMessageAsync, state, stopSpeaking, toggleMute]
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
