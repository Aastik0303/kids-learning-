import { useCallback, useEffect, useRef, useState } from "react";

import { useGuide } from "@/ai/GuideProvider";
import { ApiError } from "@/services/api/client";
import { learningApi } from "@/services/api/learningApi";
import { toddlerApi } from "@/services/api/toddlerApi";
import { track } from "@/services/analytics/analytics";
import { haptics } from "@/services/audio/haptics";
import { useChildStore } from "@/store/childStore";
import { useSessionStore } from "@/store/sessionStore";
import { useUiStore } from "@/store/uiStore";
import { voiceController } from "@/features/voice/VoiceController";
import {
  toRenderableActivity,
  toddlerToRenderableActivity,
  type RenderableActivity,
} from "@/types/activity";
import type { ActivityFeedback, AnswerMeta } from "@/activities/types";
import type { LearningResponse, ToddlerModule, ToddlerResponse } from "@/types/domain";

/**
 * Drives one lesson from start to completion (spec section 23).
 *
 *   start → question loaded → child answers → backend evaluates
 *         → AI reacts → next activity → … → complete
 *
 * Both the standard (`/learning`) and toddler (`/toddler`) backends are
 * handled here behind one interface, because from the renderer's point of
 * view they are the same thing: an activity, an answer, a verdict.
 *
 * Correctness, stars, scoring and unlocking all come from the server.
 * Nothing in this hook decides whether an answer was right.
 */

export type LessonMode = "standard" | "toddler";

export type LessonSummary = {
  starsEarned: number;
  correctCount: number;
  totalCount: number;
};

export type UseLessonSessionInput = {
  pathId: string;
  stageNumber: number;
  mode: LessonMode;
  module?: ToddlerModule;
  onComplete: (summary: LessonSummary) => void;
};

export function useLessonSession({
  pathId,
  stageNumber,
  mode,
  module,
  onComplete,
}: UseLessonSessionInput) {
  const { dispatch, say } = useGuide();
  const child = useChildStore((state) => state.activeChild);

  const [activity, setActivity] = useState<RenderableActivity | null>(null);
  const [feedback, setFeedback] = useState<ActivityFeedback | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tally kept locally purely for the recap screen. The authoritative
  // star count lives on the child profile the backend returns.
  const tally = useRef({ correct: 0, total: 0, stars: 0 });
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      void voiceController.stopAll();
    };
  }, []);

  /** Apply a standard-path response to local state. */
  const applyLearning = useCallback(
    async (response: LearningResponse, isFirst: boolean) => {
      const session = useSessionStore.getState();

      if (response.stars_earned > 0) {
        tally.current.stars += response.stars_earned;
        session.addStars(response.stars_earned);
      }

      if (response.complete || response.stage_completed) {
        onComplete({
          starsEarned: tally.current.stars,
          correctCount: tally.current.correct,
          totalCount: tally.current.total,
        });
        return;
      }

      if (!response.activity) return;

      const next = toRenderableActivity(response.activity);
      setActivity(next);
      session.setActivity(next);
      setFeedback(null);

      await dispatch(isFirst ? "LESSON_STARTED" : "QUESTION_LOADED", { surface: "lesson" });
      // Read the question aloud after the guide's own line.
      await say(next.speech || next.prompt);
    },
    [dispatch, say, onComplete],
  );

  /** Apply a toddler response to local state. */
  const applyToddler = useCallback(
    async (response: ToddlerResponse, isFirst: boolean) => {
      const session = useSessionStore.getState();

      if (response.stars_earned > 0) {
        tally.current.stars += response.stars_earned;
        session.addStars(response.stars_earned);
      }

      if (response.level_completed) {
        onComplete({
          starsEarned: tally.current.stars,
          correctCount: tally.current.correct,
          totalCount: tally.current.total,
        });
        return;
      }

      if (!response.activity) return;

      const next = toddlerToRenderableActivity(response.activity);
      setActivity(next);
      session.setActivity(next);
      setFeedback(null);

      // The toddler backend already returns a scripted guide line; using
      // it avoids an unnecessary LLM round-trip for the youngest children.
      if (response.guide.speech) {
        await say(response.guide.speech);
      } else {
        await dispatch(isFirst ? "LESSON_STARTED" : "QUESTION_LOADED", { surface: "lesson" });
      }
    },
    [dispatch, say, onComplete],
  );

  // ── Start ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!child) return;
    let cancelled = false;

    (async () => {
      setIsLoading(true);
      setError(null);
      tally.current = { correct: 0, total: 0, stars: 0 };

      try {
        if (mode === "toddler") {
          const response = await toddlerApi.start(
            child.child_id,
            module ?? "alphabets",
            stageNumber,
          );
          if (cancelled || !isMounted.current) return;
          useSessionStore.getState().begin({
            kind: "toddler",
            sessionId: response.session_id,
            childId: child.child_id,
            pathId: response.module,
            stageNumber: response.level,
            learningMode: "toddler",
          });
          await applyToddler(response, true);
        } else {
          const response = await learningApi.start(child.child_id, pathId, stageNumber);
          if (cancelled || !isMounted.current) return;
          useSessionStore.getState().begin({
            kind: "lesson",
            sessionId: response.session_id,
            childId: child.child_id,
            pathId: response.path_id,
            stageNumber: response.stage_number,
            learningMode: "standard",
          });
          await applyLearning(response, true);
        }

        track("lesson_started", { path_id: pathId, stage: stageNumber, mode });
      } catch (caught) {
        if (cancelled || !isMounted.current) return;
        setError(
          caught instanceof ApiError
            ? caught.childMessage
            : "We could not start this lesson. Let us try again!",
        );
      } finally {
        if (!cancelled && isMounted.current) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // Restarting on a new path/stage is intended; the callbacks are stable
    // enough that including them would re-run the lesson on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [child?.child_id, pathId, stageNumber, mode, module]);

  // ── Answer ────────────────────────────────────────────────────────────
  const submitAnswer = useCallback(
    async (answer: string, meta?: AnswerMeta) => {
      const session = useSessionStore.getState();
      if (!session.sessionId || isSubmitting) return;

      setIsSubmitting(true);
      session.setSubmitting(true);
      session.recordAttempt(answer);
      tally.current.total += 1;

      try {
        if (session.kind === "toddler") {
          const response = await toddlerApi.answer(
            session.sessionId,
            answer,
            meta?.transcript ?? answer,
          );
          if (!isMounted.current) return;

          const isCorrect = response.evaluation?.result === "correct";
          recordVerdict(isCorrect);

          setFeedback({
            isCorrect,
            message: response.guide.speech,
            attempt: response.attempt_count,
            questionChanged: response.question_changed,
          });

          track("answer_submitted", {
            activity_kind: activity?.kind ?? "unknown",
            input: meta?.input ?? "tap",
            correct: isCorrect,
          });

          if (response.guide.speech) await say(response.guide.speech);
          if (isCorrect || response.guide.action === "next_activity") {
            await applyToddler(response, false);
          }
        } else {
          const response = await learningApi.answer(session.sessionId, answer);
          if (!isMounted.current) return;

          const isCorrect = response.is_correct === true;
          recordVerdict(isCorrect);

          setFeedback({
            isCorrect,
            message: response.feedback,
            hint: response.activity?.hint,
            attempt: response.attempt_number,
            questionChanged: response.question_changed,
          });

          track("answer_submitted", {
            activity_kind: activity?.kind ?? "unknown",
            input: meta?.input ?? "tap",
            correct: isCorrect,
          });

          await dispatch(isCorrect ? "ANSWER_CORRECT" : "ANSWER_INCORRECT", {
            surface: "lesson",
            childAnswer: answer,
          });

          if (isCorrect) {
            if (response.stars_earned > 0) {
              useUiStore.getState().celebrate({
                kind: "stars",
                title: "You earned a star!",
                stars: response.stars_earned,
              });
            }
            await applyLearning(response, false);
          } else if (response.question_changed && response.activity) {
            // The backend served a different question after repeated
            // failures — follow it rather than keeping the old one.
            await applyLearning(response, false);
          }
        }
      } catch (caught) {
        if (!isMounted.current) return;
        setError(
          caught instanceof ApiError
            ? caught.childMessage
            : "We could not send that answer. Let us try again!",
        );
      } finally {
        if (isMounted.current) {
          setIsSubmitting(false);
          useSessionStore.getState().setSubmitting(false);
        }
      }
    },
    [activity?.kind, applyLearning, applyToddler, dispatch, isSubmitting, say],
  );

  function recordVerdict(isCorrect: boolean) {
    if (isCorrect) {
      tally.current.correct += 1;
      haptics.success();
    } else {
      haptics.gentleRetry();
    }
  }

  // ── Continue past a non-question beat ────────────────────────────────
  const continueLesson = useCallback(async () => {
    const session = useSessionStore.getState();
    if (!session.sessionId) return;

    setIsSubmitting(true);
    try {
      if (session.kind === "toddler") {
        const response = await toddlerApi.answer(session.sessionId, "", "");
        if (isMounted.current) await applyToddler(response, false);
      } else {
        const response = await learningApi.continue(session.sessionId);
        if (isMounted.current) await applyLearning(response, false);
      }
    } catch (caught) {
      if (isMounted.current) {
        setError(
          caught instanceof ApiError ? caught.childMessage : "Let us try that again!",
        );
      }
    } finally {
      if (isMounted.current) setIsSubmitting(false);
    }
  }, [applyLearning, applyToddler]);

  const repeatPrompt = useCallback(async () => {
    if (activity) await say(activity.speech || activity.prompt);
  }, [activity, say]);

  return {
    activity,
    feedback,
    isLoading,
    isSubmitting,
    error,
    submitAnswer,
    continueLesson,
    repeatPrompt,
    clearError: () => setError(null),
  };
}
