import {
  ExpoSpeechRecognitionModule,
  addSpeechRecognitionListener,
} from "@jamsch/expo-speech-recognition";
import type { EventSubscription } from "expo-modules-core";

import { languageTag } from "@/services/audio/language";

/**
 * Speech-to-text wrapper.
 *
 * Everything here is defensive: STT is the single most failure-prone part
 * of the product (no recogniser installed, permission denied, offline, a
 * child who says nothing). Each failure mode is reported as a typed
 * outcome so the UI can offer the tap fallback instead of a dead end.
 */

export type SttOutcome =
  | {
      status: "ok";
      transcript: string;
      confidence: number;
      /**
       * The recogniser's other guesses at the same utterance, best first.
       * A child saying "A" is very often the second alternative, and throwing
       * these away was throwing away answers.
       */
      alternatives: string[];
    }
  | { status: "no_speech" }
  | { status: "permission_denied" }
  | { status: "unavailable" }
  | { status: "aborted" }
  | { status: "error"; code: string };

export type SttHandlers = {
  onPartial?: (text: string) => void;
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
};

/** Detects whether the device can do STT at all. */
export function isSttAvailable(): boolean {
  try {
    return typeof ExpoSpeechRecognitionModule?.start === "function";
  } catch {
    return false;
  }
}

export async function requestSttPermission(): Promise<"granted" | "denied" | "unavailable"> {
  if (!isSttAvailable()) return "unavailable";
  try {
    const result = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    return result.granted ? "granted" : "denied";
  } catch {
    return "unavailable";
  }
}

export async function getSttPermission(): Promise<"granted" | "denied" | "unavailable"> {
  if (!isSttAvailable()) return "unavailable";
  try {
    const result = await ExpoSpeechRecognitionModule.getPermissionsAsync();
    if (result.granted) return "granted";
    return result.canAskAgain ? "denied" : "denied";
  } catch {
    return "unavailable";
  }
}

export type ListenOptions = {
  language?: string;
  /** Hard stop, so a silent child never leaves the mic open forever. */
  timeoutMs?: number;
  /** Answer candidates, used as recogniser hints where supported. */
  contextualStrings?: string[];
};

const DEFAULT_TIMEOUT = 7000;

/**
 * After the soft timeout we ask the recogniser to stop and hand back what it
 * has. If it never answers — which happens on Android when the service dies
 * mid-session — nothing else would ever settle this promise and the mic stays
 * open across the next question. This is the backstop for that.
 */
const HARD_STOP_GRACE = 1500;

/**
 * `end` sometimes arrives a beat before the final `result`. Settling as
 * "no speech" the instant `end` fires discards a transcript that was already
 * on its way, which reads to a child as the app ignoring them.
 */
const END_GRACE = 300;

/**
 * Android's recogniser reports confidence 0 for a perfectly good transcript
 * on most devices — it simply does not compute one. Zero is not "the child
 * mumbled", it is "no opinion", and passing it on gets a clear answer thrown
 * away as a mishearing downstream. A neutral value says the same thing
 * honestly.
 */
const NO_OPINION_CONFIDENCE = 0.6;

function usableConfidence(value: unknown): number {
  return typeof value === "number" && value > 0 ? value : NO_OPINION_CONFIDENCE;
}

/**
 * Capture one utterance. Resolves exactly once, and always cleans up its
 * listeners and the native session — a leaked recogniser holds the mic
 * open and blocks the next question.
 */
export function listenOnce(
  options: ListenOptions = {},
  handlers: SttHandlers = {},
): Promise<SttOutcome> {
  if (!isSttAvailable()) {
    return Promise.resolve({ status: "unavailable" });
  }

  return new Promise<SttOutcome>((resolve) => {
    const subscriptions: EventSubscription[] = [];
    const pending: ReturnType<typeof setTimeout>[] = [];
    let settled = false;
    let bestTranscript = "";
    let bestConfidence = NO_OPINION_CONFIDENCE;
    let alternatives: string[] = [];

    const timer = setTimeout(() => {
      // Ask for a final result rather than hard-aborting: the recogniser
      // often has a usable partial it will hand back on stop().
      try {
        ExpoSpeechRecognitionModule.stop();
        // ...and settle anyway if stop() is never answered.
        later(() => finish(bestTranscript ? okOutcome() : { status: "no_speech" }), HARD_STOP_GRACE);
      } catch {
        finish(bestTranscript ? okOutcome() : { status: "no_speech" });
      }
    }, options.timeoutMs ?? DEFAULT_TIMEOUT);

    function later(run: () => void, delay: number) {
      if (settled) return;
      pending.push(setTimeout(run, delay));
    }

    function okOutcome(): SttOutcome {
      return {
        status: "ok",
        transcript: bestTranscript,
        confidence: bestConfidence,
        alternatives,
      };
    }

    function finish(outcome: SttOutcome) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      pending.forEach(clearTimeout);
      subscriptions.forEach((sub) => sub.remove());
      try {
        ExpoSpeechRecognitionModule.abort();
      } catch {
        // Session already closed.
      }
      resolve(outcome);
    }

    subscriptions.push(
      addSpeechRecognitionListener("result", (event) => {
        const first = event.results?.[0];
        if (!first) return;

        if (first.transcript) {
          bestTranscript = first.transcript;
          bestConfidence = usableConfidence(first.confidence);
          alternatives = (event.results ?? [])
            .slice(1)
            .map((result) => result?.transcript ?? "")
            .filter((text) => text.trim().length > 0)
            .slice(0, 4);
        }

        if (event.isFinal) {
          finish(bestTranscript ? okOutcome() : { status: "no_speech" });
        } else if (first.transcript) {
          handlers.onPartial?.(first.transcript);
        }
      }),
    );

    subscriptions.push(
      addSpeechRecognitionListener("error", (event) => {
        const code = String(event.error ?? "unknown");
        if (code === "not-allowed" || code === "service-not-allowed") {
          finish({ status: "permission_denied" });
        } else if (code === "no-speech") {
          finish({ status: "no_speech" });
        } else if (code === "aborted") {
          finish({ status: "aborted" });
        } else {
          finish({ status: "error", code });
        }
      }),
    );

    subscriptions.push(
      addSpeechRecognitionListener("nomatch", () => {
        finish(bestTranscript ? okOutcome() : { status: "no_speech" });
      }),
    );

    subscriptions.push(
      addSpeechRecognitionListener("end", () => {
        // `end` fires after `result` in the happy path. When it arrives first,
        // give the final result its moment before calling it silence.
        if (bestTranscript) {
          finish(okOutcome());
          return;
        }
        later(() => finish(bestTranscript ? okOutcome() : { status: "no_speech" }), END_GRACE);
      }),
    );

    subscriptions.push(
      addSpeechRecognitionListener("speechstart", () => handlers.onSpeechStart?.()),
    );
    subscriptions.push(
      addSpeechRecognitionListener("speechend", () => handlers.onSpeechEnd?.()),
    );

    try {
      ExpoSpeechRecognitionModule.start({
        // Through `languageTag`, always. The recogniser needs BCP-47 and
        // refuses to start on anything else - and callers hand it the child
        // profile's display name ("English", "Hindi"), which is exactly what
        // it refuses. A refused start is a microphone that never answers.
        lang: languageTag(options.language),
        interimResults: true,
        maxAlternatives: 3,
        continuous: false,
        // Bias the recogniser toward this question's valid answers.
        contextualStrings: options.contextualStrings?.slice(0, 20),
        androidIntentOptions: {
          // A four-year-old takes a breath in the middle of "a... apple".
          // Android's defaults (around half a second) cut them off mid-answer
          // and hand back the first half of the word.
          EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS: 2000,
          EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS: 2000,
          // And they take a while to start, too.
          EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS: 1500,
        },
      });
    } catch {
      finish({ status: "unavailable" });
    }
  });
}

export function abortListening(): void {
  try {
    ExpoSpeechRecognitionModule.abort();
  } catch {
    // Nothing running.
  }
}
