import { useCallback } from "react";

import { useGuide } from "@/ai/GuideProvider";
import { track } from "@/services/analytics/analytics";
import { currentRouteName } from "@/navigation/navigationRef";
import { useChildStore } from "@/store/childStore";
import { useGuideStore } from "@/store/guideStore";
import { useSessionStore } from "@/store/sessionStore";
import { voiceController } from "@/features/voice/VoiceController";

/**
 * Hand Raise / Doubt Mode (spec section 13).
 *
 *   Lesson → ✋ → pause (state kept) → listen → AI explains
 *          → understood? → resume the exact step, or re-explain simpler
 *
 * The critical property is that pausing never unmounts or reloads the
 * activity. `sessionStore.pause()` freezes the session and keeps the
 * current activity mounted, so "resume" genuinely returns the child to the
 * same question at the same attempt count.
 */

const INVITE_LINE = "I am listening. What would you like to ask?";
const NOT_HEARD_LINE = "I did not hear that. Can you say it again?";
const RESUME_LINE = "Great! Let us keep going.";

export function useHandRaise() {
  const { dispatch, say } = useGuide();

  /** Freeze the lesson and invite the child to speak their doubt. */
  const raiseHand = useCallback(async () => {
    const session = useSessionStore.getState();
    const guide = useGuideStore.getState();

    if (guide.doubtPhase !== "idle") return;

    track("hand_raised", {
      screen: currentRouteName(),
      activity_kind: session.activity?.kind ?? null,
    });

    // Stop whatever the avatar was saying and freeze the lesson.
    await voiceController.stopAll();
    session.pause();
    guide.setDoubtPhase("asking");
    guide.setAvatarState("encouraging");

    await say(INVITE_LINE);

    // ── Listen for the doubt ───────────────────────────────────────────
    useGuideStore.getState().setDoubtPhase("listening");
    const child = useChildStore.getState().activeChild;
    const heard = await voiceController.captureAnswer(
      session.activity,
      child?.preferred_language,
    );

    if (!heard.transcript.trim()) {
      useGuideStore.getState().setDoubtPhase("asking");
      await say(NOT_HEARD_LINE);
      // Leave the child in "asking" so they can tap the mic and retry
      // rather than being dumped back into the question unhelped.
      return;
    }

    useGuideStore.getState().appendMessage("child", heard.transcript);
    useGuideStore.getState().setDoubtPhase("thinking");

    // The full lesson context travels automatically: the dispatcher reads
    // activity, attempt, recent answers and progress from the stores.
    await dispatch("DOUBT_ASKED", {
      childAnswer: heard.transcript,
      surface: "lesson",
    });

    useGuideStore.getState().setDoubtPhase("explaining");
  }, [dispatch, say]);

  /** Child understood — return to the exact paused step. */
  const resume = useCallback(async () => {
    const guide = useGuideStore.getState();
    guide.setDoubtPhase("idle");
    guide.clearHighlights();
    useSessionStore.getState().resume();
    await say(RESUME_LINE);

    // Re-read the question so the child re-enters with the prompt fresh.
    const activity = useSessionStore.getState().activity;
    if (activity) {
      await say(activity.speech || activity.prompt);
    }
  }, [say]);

  /** Child still lost — ask the agent for a simpler explanation. */
  const explainAgain = useCallback(async () => {
    useGuideStore.getState().setDoubtPhase("thinking");
    useGuideStore.getState().appendMessage("child", "I still do not understand.");

    await dispatch("HINT_REQUESTED", { surface: "lesson" });

    useGuideStore.getState().setDoubtPhase("explaining");
  }, [dispatch]);

  /** Tap the mic again during "asking" without restarting the whole flow. */
  const listenAgain = useCallback(async () => {
    const session = useSessionStore.getState();
    const child = useChildStore.getState().activeChild;

    useGuideStore.getState().setDoubtPhase("listening");
    const heard = await voiceController.captureAnswer(
      session.activity,
      child?.preferred_language,
    );

    if (!heard.transcript.trim()) {
      useGuideStore.getState().setDoubtPhase("asking");
      await say(NOT_HEARD_LINE);
      return;
    }

    useGuideStore.getState().appendMessage("child", heard.transcript);
    useGuideStore.getState().setDoubtPhase("thinking");
    await dispatch("DOUBT_ASKED", { childAnswer: heard.transcript, surface: "lesson" });
    useGuideStore.getState().setDoubtPhase("explaining");
  }, [dispatch, say]);

  /** Escape hatch — close doubt mode without an explanation. */
  const cancel = useCallback(async () => {
    await voiceController.stopAll();
    useGuideStore.getState().setDoubtPhase("idle");
    useSessionStore.getState().resume();
  }, []);

  return { raiseHand, resume, explainAgain, listenAgain, cancel };
}
