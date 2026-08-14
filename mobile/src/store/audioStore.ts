import { create } from "zustand";

import { kv, storageKeys } from "@/services/storage/kv";

/**
 * Voice pipeline state (spec section 12).
 *
 * The invariant this store exists to protect: the microphone is never open
 * while the avatar is speaking. `isSpeaking` and `isListening` must not
 * both be true, or the app transcribes its own TTS output.
 */

export type MicPermission = "unknown" | "granted" | "denied" | "unavailable";

export type ListeningOutcome =
  | "idle"
  | "captured"
  | "no_speech"
  | "too_quiet"
  | "permission_denied"
  | "unavailable"
  /** Cancelled before a result — e.g. Hand Raise interrupted the capture. */
  | "aborted"
  | "error";

type AudioState = {
  isSpeaking: boolean;
  isListening: boolean;
  /** Set while TTS is winding down, before the mic may reopen. */
  isSettling: boolean;

  muted: boolean;
  /** Device TTS vs the backend's hosted voice. */
  voiceProvider: "device" | "hosted";

  micPermission: MicPermission;
  partialTranscript: string;
  finalTranscript: string;
  confidence: number;
  lastOutcome: ListeningOutcome;

  setSpeaking: (value: boolean) => void;
  setSettling: (value: boolean) => void;
  setListening: (value: boolean) => void;
  setMicPermission: (value: MicPermission) => void;
  setPartial: (text: string) => void;
  setFinal: (text: string, confidence: number) => void;
  setOutcome: (outcome: ListeningOutcome) => void;
  clearTranscript: () => void;
  toggleMute: () => void;
  setVoiceProvider: (provider: "device" | "hosted") => void;
  loadPrefs: () => Promise<void>;
  /** True when it is safe to open the microphone right now. */
  canListen: () => boolean;
};

export const useAudioStore = create<AudioState>((set, get) => ({
  isSpeaking: false,
  isListening: false,
  isSettling: false,
  muted: false,
  voiceProvider: "device",
  micPermission: "unknown",
  partialTranscript: "",
  finalTranscript: "",
  confidence: 0,
  lastOutcome: "idle",

  setSpeaking(value) {
    // Opening TTS force-closes any listening state as a hard guarantee.
    set(value ? { isSpeaking: true, isListening: false } : { isSpeaking: false });
  },

  setSettling(isSettling) {
    set({ isSettling });
  },

  setListening(value) {
    // Refuse to enter listening while TTS is active or settling.
    if (value && (get().isSpeaking || get().isSettling)) return;
    set({ isListening: value });
  },

  setMicPermission(micPermission) {
    set({ micPermission });
  },

  setPartial(partialTranscript) {
    set({ partialTranscript });
  },

  setFinal(finalTranscript, confidence) {
    set({ finalTranscript, confidence, partialTranscript: "" });
  },

  setOutcome(lastOutcome) {
    set({ lastOutcome });
  },

  clearTranscript() {
    set({ partialTranscript: "", finalTranscript: "", confidence: 0, lastOutcome: "idle" });
  },

  toggleMute() {
    const muted = !get().muted;
    set({ muted });
    void kv.set(storageKeys.audioPrefs, { muted, voiceProvider: get().voiceProvider });
  },

  setVoiceProvider(voiceProvider) {
    set({ voiceProvider });
    void kv.set(storageKeys.audioPrefs, { muted: get().muted, voiceProvider });
  },

  async loadPrefs() {
    const prefs = await kv.get<{ muted: boolean; voiceProvider: "device" | "hosted" }>(
      storageKeys.audioPrefs,
    );
    if (prefs) {
      set({ muted: prefs.muted, voiceProvider: prefs.voiceProvider });
    }
  },

  canListen() {
    const state = get();
    return (
      !state.isSpeaking &&
      !state.isSettling &&
      !state.isListening &&
      state.micPermission !== "denied" &&
      state.micPermission !== "unavailable"
    );
  },
}));
