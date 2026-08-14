import {
  ExpoSpeechRecognitionModule,
  addSpeechRecognitionListener,
} from "@jamsch/expo-speech-recognition";
import type { EventSubscription } from "expo-modules-core";

/**
 * Speech-to-text wrapper.
 *
 * Everything here is defensive: STT is the single most failure-prone part
 * of the product (no recogniser installed, permission denied, offline, a
 * child who says nothing). Each failure mode is reported as a typed
 * outcome so the UI can offer the tap fallback instead of a dead end.
 */

export type SttOutcome =
  | { status: "ok"; transcript: string; confidence: number }
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
    let settled = false;
    let bestTranscript = "";
    let bestConfidence = 0;

    const timer = setTimeout(() => {
      // Ask for a final result rather than hard-aborting: the recogniser
      // often has a usable partial it will hand back on stop().
      try {
        ExpoSpeechRecognitionModule.stop();
      } catch {
        finish(bestTranscript ? okOutcome() : { status: "no_speech" });
      }
    }, options.timeoutMs ?? DEFAULT_TIMEOUT);

    function okOutcome(): SttOutcome {
      return { status: "ok", transcript: bestTranscript, confidence: bestConfidence };
    }

    function finish(outcome: SttOutcome) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
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
          bestConfidence = typeof first.confidence === "number" ? first.confidence : 0.6;
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
        // `end` fires after `result` in the happy path; if we get here
        // without a final result, take whatever we heard.
        finish(bestTranscript ? okOutcome() : { status: "no_speech" });
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
        lang: options.language ?? "en-US",
        interimResults: true,
        maxAlternatives: 3,
        continuous: false,
        // Bias the recogniser toward this question's valid answers.
        contextualStrings: options.contextualStrings?.slice(0, 20),
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
