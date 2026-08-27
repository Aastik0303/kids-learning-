import * as Speech from "expo-speech";
import { createAudioPlayer, type AudioPlayer } from "expo-audio";

import { isEnabled } from "@/config/featureFlags";
import { languageTag, segmentByScript } from "@/services/audio/language";
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
  /**
   * An exact BCP-47 tag for this one utterance, overriding `language`. Set by
   * the script splitter so a Devanagari run is read by a Hindi voice.
   */
  tag?: string;
  /** Slower than default: young children need time to parse each word. */
  rate?: number;
  pitch?: number;
  onStart?: () => void;
  onDone?: () => void;
};

const CHILD_RATE = 0.86;
const CHILD_PITCH = 1.08;

let activePlayer: AudioPlayer | null = null;

/**
 * Bumped by every `speak` and every `stop`. A mixed-script line is spoken as
 * several sequential utterances, and `Speech.stop()` only ends the one that is
 * playing - without this the loop would calmly start the next segment, so a
 * child tapping to interrupt would still hear the rest of the sentence.
 */
let utterance = 0;

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
      language: options.tag ?? languageTag(options.language),
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
    const mine = ++utterance;

    if (provider === "hosted" && isEnabled("elevenLabsVoice")) {
      // The hosted voice is multilingual, so a mixed line goes to it whole.
      const played = await speakHosted(clean, options);
      if (played) return;
      // Hosted failed — fall through to device rather than going silent.
    }

    // The device voice is not. An English engine handed "This is अ." reads
    // "This is." and drops the letter the whole level is about, so the line is
    // split and each run is spoken by a voice that can read it.
    const base = languageTag(options.language);
    const segments = segmentByScript(clean, base);

    for (const [index, segment] of segments.entries()) {
      if (mine !== utterance) return; // Interrupted between segments.
      await speakOnDevice(segment.text, {
        ...options,
        tag: segment.tag,
        // The callbacks belong to the utterance, not to each of its pieces.
        onStart: index === 0 ? options.onStart : undefined,
        onDone: index === segments.length - 1 ? options.onDone : undefined,
      });
    }
  },

  async stop(): Promise<void> {
    utterance += 1;
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
