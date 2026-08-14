import { isEnabled } from "@/config/featureFlags";
import { track } from "@/services/analytics/analytics";
import { haptics } from "@/services/audio/haptics";
import {
  abortListening,
  getSttPermission,
  isSttAvailable,
  listenOnce,
  requestSttPermission,
  type SttOutcome,
} from "@/services/audio/stt";
import { tts } from "@/services/audio/tts";
import { speechApi } from "@/services/api/speechApi";
import { useAudioStore } from "@/store/audioStore";
import { useGuideStore } from "@/store/guideStore";
import type { RenderableActivity } from "@/types/activity";

/**
 * ═══ THE VOICE PIPELINE (spec section 12) ═══
 *
 *   AI speaking → mic OFF → TTS ends → settle → mic ON → child speaks
 *   → STT → normalise against the question → answer
 *
 * The hard invariant: the microphone is never open while the avatar is
 * speaking, or the app transcribes its own voice and "hears" the answer it
 * just gave away. Two mechanisms enforce it:
 *
 *   1. `audioStore.setListening` refuses to enter listening while
 *      `isSpeaking` or `isSettling` is true.
 *   2. `SETTLE_MS` below holds the mic shut after TTS reports completion,
 *      because speaker output trails the callback on most devices.
 */

const SETTLE_MS = 280;

/** Below this, treat the transcript as a mishearing rather than an answer. */
const MIN_CONFIDENCE = 0.35;

export type VoiceAnswer = {
  /** What the recogniser heard, verbatim. */
  transcript: string;
  /** Resolved against the question's candidates by the backend. */
  resolvedAnswer: string;
  confidence: number;
  /** True when the transcript matched a real answer candidate. */
  isResolved: boolean;
  outcome: SttOutcome["status"];
};

export const voiceController = {
  /** Ask for microphone + speech permission, caching the result in the store. */
  async ensurePermission(): Promise<boolean> {
    const store = useAudioStore.getState();

    if (!isSttAvailable() || !isEnabled("voiceInput")) {
      store.setMicPermission("unavailable");
      return false;
    }

    if (store.micPermission === "granted") return true;

    const existing = await getSttPermission();
    if (existing === "granted") {
      store.setMicPermission("granted");
      return true;
    }
    if (existing === "unavailable") {
      store.setMicPermission("unavailable");
      return false;
    }

    const requested = await requestSttPermission();
    store.setMicPermission(requested === "granted" ? "granted" : requested);
    return requested === "granted";
  },

  /**
   * Speak through the avatar. Holds `isSpeaking` for the whole utterance
   * and then `isSettling` through the trailing-audio window.
   */
  async speak(text: string, language?: string): Promise<void> {
    const store = useAudioStore.getState();
    if (store.muted || !isEnabled("voiceOutput")) return;
    if (!text.trim()) return;

    store.setSpeaking(true);
    try {
      await tts.speak(text, store.voiceProvider, { language });
    } finally {
      store.setSpeaking(false);
      store.setSettling(true);
      await new Promise((resolve) => setTimeout(resolve, SETTLE_MS));
      useAudioStore.getState().setSettling(false);
    }
  },

  /** Cut speech off immediately — used when the child taps to interrupt. */
  async stopSpeaking(): Promise<void> {
    await tts.stop();
    const store = useAudioStore.getState();
    store.setSpeaking(false);
    store.setSettling(false);
  },

  /**
   * Open the microphone for one answer, then resolve the transcript
   * against this question's candidates via POST /speech/normalize.
   *
   * Normalisation is what turns a child saying "tree" into the answer "3".
   * It is deterministic backend code, not an LLM judgement.
   */
  async captureAnswer(activity: RenderableActivity | null, language?: string): Promise<VoiceAnswer> {
    const store = useAudioStore.getState();

    const permitted = await voiceController.ensurePermission();
    if (!permitted) {
      store.setOutcome(
        store.micPermission === "unavailable" ? "unavailable" : "permission_denied",
      );
      return emptyAnswer(store.micPermission === "unavailable" ? "unavailable" : "permission_denied");
    }

    if (!store.canListen()) {
      // Something is still speaking. Refusing beats racing the speaker.
      return emptyAnswer("aborted");
    }

    store.clearTranscript();
    store.setListening(true);
    // Mirror the mic state on the avatar so the child sees it is their turn.
    useGuideStore.getState().setAvatarState("listening");
    haptics.listenStart();

    const candidates = activity
      ? [activity.correctAnswer, ...activity.acceptedAnswers, ...activity.options].filter(Boolean)
      : [];

    const outcome = await listenOnce(
      {
        language,
        contextualStrings: candidates,
        timeoutMs: 8000,
      },
      {
        onPartial: (text) => useAudioStore.getState().setPartial(text),
      },
    );

    useAudioStore.getState().setListening(false);

    if (outcome.status !== "ok") {
      useAudioStore.getState().setOutcome(outcome.status === "error" ? "error" : outcome.status);
      track("voice_capture", { outcome: outcome.status, confidence: 0 });
      return emptyAnswer(outcome.status);
    }

    useAudioStore.getState().setFinal(outcome.transcript, outcome.confidence);

    if (outcome.confidence > 0 && outcome.confidence < MIN_CONFIDENCE) {
      useAudioStore.getState().setOutcome("too_quiet");
      track("voice_capture", { outcome: "too_quiet", confidence: outcome.confidence });
      return {
        transcript: outcome.transcript,
        resolvedAnswer: "",
        confidence: outcome.confidence,
        isResolved: false,
        outcome: "ok",
      };
    }

    // Resolve the raw transcript against this question's real candidates.
    try {
      const resolution = await speechApi.normalize({
        transcript: outcome.transcript,
        confidence: outcome.confidence,
        answer_type: activity?.kind ?? "",
        activity_id: activity?.id ?? null,
        correct_answer: activity?.correctAnswer ?? null,
        accepted_answers: activity?.acceptedAnswers ?? [],
        options: activity?.options ?? [],
      });

      useAudioStore.getState().setOutcome("captured");
      track("voice_capture", { outcome: "captured", confidence: outcome.confidence });

      return {
        transcript: outcome.transcript,
        resolvedAnswer: resolution.resolved_answer,
        confidence: resolution.resolution_confidence,
        isResolved: resolution.input_kind === "answer" && !resolution.ambiguous,
        outcome: "ok",
      };
    } catch {
      // Normalisation unreachable — fall back to the raw transcript so a
      // network blip does not discard what the child actually said.
      useAudioStore.getState().setOutcome("captured");
      return {
        transcript: outcome.transcript,
        resolvedAnswer: outcome.transcript.trim(),
        confidence: outcome.confidence,
        isResolved: false,
        outcome: "ok",
      };
    }
  },

  /**
   * The canonical teach-then-listen beat: say the prompt, wait for audio
   * to finish, then open the mic.
   */
  async speakThenListen(
    text: string,
    activity: RenderableActivity | null,
    language?: string,
  ): Promise<VoiceAnswer> {
    await voiceController.speak(text, language);
    return voiceController.captureAnswer(activity, language);
  },

  /** Hard stop everything. Called on unmount, background and Hand Raise. */
  async stopAll(): Promise<void> {
    abortListening();
    await tts.stop();
    const store = useAudioStore.getState();
    store.setListening(false);
    store.setSpeaking(false);
    store.setSettling(false);
  },
};

function emptyAnswer(outcome: SttOutcome["status"]): VoiceAnswer {
  return { transcript: "", resolvedAnswer: "", confidence: 0, isResolved: false, outcome };
}
