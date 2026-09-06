import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/services/api/client";
import { conductorApi } from "@/services/api/conductorApi";
import { track } from "@/services/analytics/analytics";
import { haptics } from "@/services/audio/haptics";
import { voiceController } from "@/features/voice/VoiceController";
import { useChildStore } from "@/store/childStore";
import { useGuideStore } from "@/store/guideStore";
import { conductorToRenderableActivity, type RenderableActivity } from "@/types/activity";
import type { ConductorClose, ConductorDirective, ConductorInputPayload } from "@/types/domain";

/**
 * Drives one sitting of the conducted class.
 *
 * The shape of this hook is the whole point of the conductor, so it is worth
 * saying plainly what it does *not* do. It does not decide whether an answer
 * was right. It does not decide what comes next, when to re-explain, when to
 * open the microphone, how long to wait, or what silence means. Every one of
 * those used to live on the device in `useLessonSession`, spread across four
 * endpoints; all of them are now one field on the directive.
 *
 * What is left is a loop, and it is the entire client half of the class:
 *
 *   1. speak `directive.speech.text`, and wait for the audio to finish
 *   2. do what `next_input.expects` says:
 *        "ready"  → the guide is still talking; carry on after
 *                   `auto_advance_in_ms`. This is where the "next" button was.
 *        "voice"  → open the microphone, send back what was heard
 *        "tap" /
 *        "trace"  → wait for the child, and report `on_timeout` if nothing comes
 *   3. send it, get the next directive, repeat
 *
 * The microphone opening by itself in step 2 is the say-it-back beat: after
 * the guide explains a thing, the server asks for it back and the mic opens
 * without the child having to find a button. `phase === "say_it"` is that beat.
 */

export type ClassSummary = {
  starsEarned: number;
  reason: ConductorClose["reason"];
  topicCompleted: boolean;
};

export type UseConductorClassInput = {
  onComplete: (summary: ClassSummary) => void;
};

export function useConductorClass({ onComplete }: UseConductorClassInput) {
  const child = useChildStore((state) => state.activeChild);

  const [directive, setDirective] = useState<ConductorDirective | null>(null);
  const [activity, setActivity] = useState<RenderableActivity | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMounted = useRef(true);
  /**
   * Every directive gets a number. Anything still in flight from an older one -
   * a pending auto-advance, an idle timer, an open microphone - checks this
   * before it acts, so a child who taps while the guide is still talking can
   * never have their answer overtaken by a timer from the previous beat.
   */
  const beat = useRef(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const shownAt = useRef(Date.now());
  const sessionId = useRef<string | null>(null);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      beat.current += 1;
      clearTimers();
      void voiceController.stopAll();
      useGuideStore.getState().clearHighlights();
    };
  }, [clearTimers]);

  // ── Sending one input ────────────────────────────────────────────────
  const send = useCallback(
    async (payload: ConductorInputPayload) => {
      const id = sessionId.current;
      if (!id) return;

      beat.current += 1;
      clearTimers();
      setIsSubmitting(true);
      try {
        const next = await conductorApi.send(id, {
          ...payload,
          latency_ms: payload.latency_ms ?? Date.now() - shownAt.current,
        });
        if (!isMounted.current) return;
        applyRef.current?.(next);
      } catch (caught) {
        if (!isMounted.current) return;
        setError(
          caught instanceof ApiError ? caught.childMessage : "Let us try that again!",
        );
      } finally {
        if (isMounted.current) setIsSubmitting(false);
      }
    },
    [clearTimers],
  );

  /**
   * `apply` and `send` call each other, which a `useCallback` pair cannot
   * express without one of them capturing a stale version of the other. The
   * ref is the smallest way to tie the knot.
   */
  const applyRef = useRef<((next: ConductorDirective) => void) | null>(null);

  // ── Rendering one directive ──────────────────────────────────────────
  const apply = useCallback(
    (next: ConductorDirective) => {
      beat.current += 1;
      const mine = beat.current;
      clearTimers();

      sessionId.current = next.session_id;
      setDirective(next);
      setActivity(
        next.activity
          ? conductorToRenderableActivity(next.activity, next.scaffold.options_shown)
          : null,
      );
      setIsLoading(false);
      shownAt.current = Date.now();

      const guide = useGuideStore.getState();
      guide.setAvatarState(next.avatar.state);
      guide.clearHighlights();

      void (async () => {
        // 1. The guide talks. The microphone stays shut for all of it — the
        //    controller refuses to listen while anything is speaking, which is
        //    what stops the app transcribing its own voice and "hearing" the
        //    answer it just gave away.
        if (next.speech.speak && next.speech.text) {
          // Deliberately **not** `speech.language`. That field is the language
          // of the topic's *content*, and on a Hindi level it says "hi" - but
          // what the guide says is an English sentence with the letter quoted
          // inside it ("This is अ. अ is for अनार."). Handing "hi" over as the
          // base would have a Hindi voice read the English half. The narration
          // is English; `tts` switches voices for the Devanagari runs by itself.
          await voiceController.speak(next.speech.text);
        }
        if (mine !== beat.current || !isMounted.current) return;

        // 2. The sitting is over.
        if (next.close) {
          track("class_closed", { reason: next.close.reason, phase: next.phase });
          onComplete({
            starsEarned: next.close.stars_earned,
            reason: next.close.reason,
            topicCompleted: next.close.topic_completed,
          });
          return;
        }

        // 3. The child's turn to speak. The mic opens by itself: a four-year-old
        //    should not have to know that a button means "now talk".
        if (next.next_input.expects === "voice") {
          const heard = await voiceController.listenForDirective({
            contextualStrings: next.listen.contextual_strings,
            language: next.listen.language,
            expect: next.listen.expect,
            timeoutMs: next.listen.hold_open_ms || next.next_input.timeout_ms,
          });
          if (mine !== beat.current || !isMounted.current) return;

          // Silence is not a wrong answer and is not the client's to interpret.
          // It goes back as the kind the server asked for on a timeout.
          if (!heard.transcript.trim()) {
            await send({ kind: next.next_input.on_timeout });
            return;
          }
          await send({
            kind: "voice",
            answer: heard.transcript,
            confidence: heard.confidence,
            alternatives: heard.alternatives,
          });
          return;
        }

        // 4. Nothing is expected: the class carries on by itself. This is the
        //    "next" button, replaced by the server's own arithmetic.
        if (next.auto_advance_in_ms !== null) {
          timers.current.push(
            setTimeout(() => {
              if (mine === beat.current && isMounted.current) void send({ kind: "ready" });
            }, next.auto_advance_in_ms),
          );
          return;
        }

        // 5. A tap or a trace. Wait for the child, and tell the server if
        //    nothing comes — it decides what that meant, not this timer.
        if (next.next_input.timeout_ms > 0) {
          timers.current.push(
            setTimeout(() => {
              if (mine === beat.current && isMounted.current) {
                void send({ kind: next.next_input.on_timeout });
              }
            }, next.next_input.timeout_ms),
          );
        }
      })();
    },
    [clearTimers, onComplete, send],
  );

  applyRef.current = apply;

  // ── Opening the class ────────────────────────────────────────────────
  useEffect(() => {
    if (!child) return;
    let cancelled = false;

    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const first = await conductorApi.open(child.child_id);
        if (cancelled || !isMounted.current) return;
        track("class_opened", { topic_id: first.topic_id, phase: first.phase });
        apply(first);
      } catch (caught) {
        if (cancelled || !isMounted.current) return;
        setIsLoading(false);
        setError(
          caught instanceof ApiError
            ? caught.childMessage
            : "We could not open your class. Let us try again!",
        );
      }
    })();

    return () => {
      cancelled = true;
    };
    // Opening is keyed on the child alone; `apply` is stable enough that
    // including it would reopen the class on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [child?.child_id]);

  // ── What the screen can do ───────────────────────────────────────────

  /**
   * The child answered with their hands - a tap, or a finished trace.
   *
   * The kind reported is the one the directive asked for. A traced letter is
   * not a tap, and telling the server it was would misreport how the child
   * answered in the very log the branch engine reads back.
   */
  const answer = useCallback(
    (value: string) => {
      haptics.tap();
      const expects = directive?.next_input.expects;
      void send({ kind: expects === "trace" ? "trace" : "tap", answer: value });
    },
    [directive, send],
  );

  /** The child pressed the microphone themselves rather than waiting. */
  const speakAnswer = useCallback(async () => {
    const current = directive;
    if (!current) return;
    const heard = await voiceController.listenForDirective({
      contextualStrings:
        current.listen.contextual_strings.length > 0
          ? current.listen.contextual_strings
          : current.scaffold.options_shown,
      language: current.listen.language,
      expect: current.listen.expect,
      timeoutMs: current.listen.hold_open_ms || current.next_input.timeout_ms,
    });
    if (!heard.transcript.trim()) return;
    await send({
      kind: "voice",
      answer: heard.transcript,
      confidence: heard.confidence,
      alternatives: heard.alternatives,
    });
  }, [directive, send]);

  /** Say the current line again. Changes nothing on the server. */
  const repeat = useCallback(async () => {
    if (directive?.speech.text) {
      // English narration, Devanagari switched per-run by `tts`. See `apply`.
      await voiceController.speak(directive.speech.text);
    }
  }, [directive]);

  /** Hand raised. The server pauses the class and keeps the place. */
  const raiseHand = useCallback(() => {
    void send({ kind: "doubt" });
  }, [send]);

  return {
    directive,
    activity,
    isLoading,
    isSubmitting,
    error,
    phase: directive?.phase ?? null,
    /** True while the class is waiting to hear the child say something back. */
    isListeningBeat: directive?.listen.active ?? false,
    answer,
    speakAnswer,
    repeat,
    raiseHand,
    clearError: () => setError(null),
  };
}
