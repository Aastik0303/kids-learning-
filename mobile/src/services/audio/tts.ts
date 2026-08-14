import * as Speech from "expo-speech";
import { createAudioPlayer, type AudioPlayer } from "expo-audio";

import { isEnabled } from "@/config/featureFlags";
import { speechApi } from "@/services/api/speechApi";

/**
 * Text-to-speech with two providers:
 *
 *   device — expo-speech. Always available, zero latency, no network.
 *   hosted — POST /speech/synthesize (ElevenLabs). Warmer voice, but the
 *            backend returns 503 without an API key, so it can never be
 *            the only path.
 *
 * Callers await `speak()` and can rely on it resolving only once audio has
 * genuinely finished — that is what lets VoiceController reopen the mic at
 * a safe moment.
 */

export type SpeakOptions = {
  language?: string;
  /** Slower than default: young children need time to parse each word. */
  rate?: number;
  pitch?: number;
  onStart?: () => void;
  onDone?: () => void;
};

const CHILD_RATE = 0.86;
const CHILD_PITCH = 1.08;

let activePlayer: AudioPlayer | null = null;

function languageTag(preferred?: string): string {
  if (!preferred) return "en-US";
  // Child profiles store a display name ("English"), not a BCP-47 tag.
  const map: Record<string, string> = {
    english: "en-US",
    hindi: "hi-IN",
    spanish: "es-ES",
    french: "fr-FR",
    arabic: "ar-SA",
  };
  return map[preferred.toLowerCase()] ?? preferred;
}

function speakOnDevice(text: string, options: SpeakOptions): Promise<void> {
  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      options.onDone?.();
      resolve();
    };

    Speech.speak(text, {
      language: languageTag(options.language),
      rate: options.rate ?? CHILD_RATE,
      pitch: options.pitch ?? CHILD_PITCH,
      onStart: options.onStart,
      onDone: finish,
      onStopped: finish,
      // A TTS engine failure must not hang the lesson waiting on a promise.
      onError: finish,
    });
  });
}

async function speakHosted(text: string, options: SpeakOptions): Promise<boolean> {
  const uri = await speechApi.synthesizeUrl(text);
  if (!uri) return false;

  return new Promise<boolean>((resolve) => {
    try {
      const player = createAudioPlayer({ uri });
      activePlayer = player;
      options.onStart?.();

      const subscription = player.addListener("playbackStatusUpdate", (status) => {
        if (status.didJustFinish) {
          subscription.remove();
          player.remove();
          if (activePlayer === player) activePlayer = null;
          options.onDone?.();
          resolve(true);
        }
      });

      player.play();
    } catch {
      resolve(false);
    }
  });
}

export const tts = {
  /**
   * Speak, resolving when audio has finished. Falls back from hosted to
   * device automatically so a missing API key is invisible to the child.
   */
  async speak(
    text: string,
    provider: "device" | "hosted",
    options: SpeakOptions = {},
  ): Promise<void> {
    const clean = text.trim();
    if (!clean) return;

    await tts.stop();

    if (provider === "hosted" && isEnabled("elevenLabsVoice")) {
      const played = await speakHosted(clean, options);
      if (played) return;
      // Hosted failed — fall through to device rather than going silent.
    }

    await speakOnDevice(clean, options);
  },

  async stop(): Promise<void> {
    if (activePlayer) {
      try {
        activePlayer.remove();
      } catch {
        // Player may already be released.
      }
      activePlayer = null;
    }
    try {
      await Speech.stop();
    } catch {
      // Nothing was speaking.
    }
  },

  isSpeaking(): Promise<boolean> {
    return Speech.isSpeakingAsync().catch(() => false);
  },
};
