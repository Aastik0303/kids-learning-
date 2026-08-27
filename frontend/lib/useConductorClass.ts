"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/services/api";
import { openClass, sendClassInput } from "@/services/conductor";
import { captureClassSpeech, speakTextAsync, stopSpeech } from "@/services/speech";
import type { ConductorDirective, ConductorInputPayload } from "@/types";

/**
 * Drives one sitting of the conducted class.
 *
 * The shape of this hook is the whole point of the conductor, so it is worth
 * saying plainly what it does *not* do. It does not decide whether an answer
 * was right. It does not decide what comes next, when to re-explain, when to
 * open the microphone, how long to wait, or what silence means. All of that
 * used to live in the lesson page, spread across four endpoints; every one of
 * them is now a field on the directive.
 *
 * What is left is a loop, and it is the entire client half of the class:
 *
 *   1. speak `speech.text`, and wait for the audio to finish
 *   2. do what `next_input.expects` says:
 *        "ready"  → the guide is still talking; carry on after
 *                   `auto_advance_in_ms`. This is where the "next" button was.
 *        "voice"  → open the microphone, send back what was heard
 *        "tap" /
 *        "trace"  → wait for the child, report `on_timeout` if nothing comes
 *   3. send it, get the next directive, repeat
 *
 * The microphone opening by itself in step 2 is the say-it-back beat: once the
 * guide has explained a letter, the server asks for it back and the mic opens
 * without the child having to find a button. `phase === "say_it"` is that beat.
 */

/**
 * The pause between the guide finishing a line and the class moving on. Short
 * enough not to be a wait, long enough that beats do not run into each other.
 */
const SETTLE_MS = 350;

export type ClassSummary = {
  starsEarned: number;
  reason: string;
  topicCompleted: boolean;
};

export function useConductorClass({
  childId,
  topicId = null,
  onComplete
}: {
  childId: string | null;
  /**
   * Which topic to conduct. Null is the normal case — the server opens whatever
   * today's plan holds. Adventure passes a level here because a grown-up picked
   * it off the map; the plan still refuses one that is not today's, and that
   * refusal arrives as `notToday` rather than as an error.
   */
  topicId?: string | null;
  onComplete: (summary: ClassSummary) => void;
}) {
  const [directive, setDirective] = useState<ConductorDirective | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notToday, setNotToday] = useState("");
  const [listening, setListening] = useState(false);

  const mounted = useRef(true);
  /**
   * Every directive gets a number. Anything still in flight from an older one —
   * a pending auto-advance, an idle timer, an open microphone — checks this
   * before acting, so a child who taps while the guide is still talking can
   * never have their answer overtaken by a timer from the previous beat.
   */
  const beat = useRef(0);
  const timers = useRef<number[]>([]);
  const shownAt = useRef(Date.now());
  const sessionId = useRef<string | null>(null);
  const applyRef = useRef<((next: ConductorDirective) => void) | null>(null);

  const clearTimers = useCallback(() => {
    timers.current.forEach((id) => window.clearTimeout(id));
    timers.current = [];
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      beat.current += 1;
      clearTimers();
      stopSpeech();
    };
  }, [clearTimers]);

  const send = useCallback(
    async (payload: ConductorInputPayload) => {
      const id = sessionId.current;
      if (!id) return;

      beat.current += 1;
      clearTimers();
      setBusy(true);
      try {
        const next = await sendClassInput(id, {
          ...payload,
          latency_ms: payload.latency_ms ?? Date.now() - shownAt.current
        });
        if (!mounted.current) return;
        applyRef.current?.(next);
      } catch {
        if (mounted.current) setError("Let us try that again!");
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [clearTimers]
  );

  const apply = useCallback(
    (next: ConductorDirective) => {
      beat.current += 1;
      const mine = beat.current;
      clearTimers();

      sessionId.current = next.session_id;
      setDirective(next);
      setLoading(false);
      shownAt.current = Date.now();

      void (async () => {
        // 1. The guide talks. The microphone stays shut for all of it, or the
        //    app transcribes its own voice and "hears" the answer it just gave.
        if (next.speech.speak && next.speech.text) {
          // Deliberately not `speech.language`. That is the language of the
          // topic's *content*, and on a Hindi level it says "hi" — but what the
          // guide says is an English sentence with the letter quoted inside it
          // ("This is अ. अ is for अनार."). `speakTextAsync` splits the line by
          // script and reads each run in a voice that can read it.
          await speakTextAsync(next.speech.text);
        }
        if (mine !== beat.current || !mounted.current) return;

        // 2. The sitting is over.
        if (next.close) {
          onComplete({
            starsEarned: next.close.stars_earned,
            reason: next.close.reason,
            topicCompleted: next.close.topic_completed
          });
          return;
        }

        // 3. The child's turn to speak. The mic opens by itself: a four-year-old
        //    should not have to know that a button means "now talk".
        if (next.next_input.expects === "voice") {
          setListening(true);
          const heard = await captureClassSpeech({
            expect: next.listen.expect,
            contextualStrings: next.listen.contextual_strings,
            language: next.listen.language,
            timeoutMs: next.listen.hold_open_ms || next.next_input.timeout_ms
          });
          if (mounted.current) setListening(false);
          if (mine !== beat.current || !mounted.current) return;

          // Silence is not a wrong answer, and not this browser's to interpret.
          // It goes back as the kind the server asked for on a timeout.
          if (!heard.transcript) {
            await send({ kind: next.next_input.on_timeout });
            return;
          }
          await send({
            kind: "voice",
            answer: heard.transcript,
            confidence: heard.confidence,
            alternatives: heard.alternatives
          });
          return;
        }

        // 4. Nothing is expected: the class carries on by itself. This is where
        //    the "next" button used to be.
        if (next.auto_advance_in_ms !== null) {
          // `auto_advance_in_ms` is the server's estimate of how long the guide
          // is talking for — roughly reading speed times the word count. Waiting
          // it out *after* the audio has finished spends it twice, and that was
          // most of the dead air at the start of a lesson: a real voice took its
          // second to arrive and its two seconds to speak, and then the class
          // sat still for another two before doing anything.
          //
          // It is a budget measured from when the beat appeared, so what is owed
          // is the remainder. A line that took longer to speak than the estimate
          // has already spent it, and only the settle beat is left.
          const spent = Date.now() - shownAt.current;
          const remaining = Math.max(SETTLE_MS, next.auto_advance_in_ms - spent);
          timers.current.push(
            window.setTimeout(() => {
              if (mine === beat.current && mounted.current) void send({ kind: "ready" });
            }, remaining)
          );
          return;
        }

        // 5. A tap or a trace. Wait for the child, and tell the server if
        //    nothing comes — it decides what that meant, not this timer.
        if (next.next_input.timeout_ms > 0) {
          timers.current.push(
            window.setTimeout(() => {
              if (mine === beat.current && mounted.current) {
                void send({ kind: next.next_input.on_timeout });
              }
            }, next.next_input.timeout_ms)
          );
        }
      })();
    },
    [clearTimers, onComplete, send]
  );

  applyRef.current = apply;

  useEffect(() => {
    if (!childId) return;
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError("");
      setNotToday("");
      try {
        const first = await openClass(childId, topicId);
        if (cancelled || !mounted.current) return;
        apply(first);
      } catch (err: unknown) {
        if (cancelled || !mounted.current) return;
        setLoading(false);
        // "Saved for tomorrow" is the schedule doing its job, not a failure.
        // The server words it for a child, so it is kept as it came.
        if (err instanceof ApiRequestError && err.code === "NOT_TODAYS_PLAN") {
          setNotToday(err.message);
          return;
        }
        setError("We could not open your class. Let us try again!");
      }
    })();

    return () => {
      cancelled = true;
    };
    // Opening is keyed on the child and the topic alone; `apply` is stable
    // enough that including it would reopen the class on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childId, topicId]);

  /**
   * The child answered with their hands. The kind reported is the one the
   * directive asked for: a traced letter is not a tap, and saying it was would
   * misreport how the child answered in the log the branch engine reads back.
   */
  const answer = useCallback(
    (value: string) => {
      const expects = directive?.next_input.expects;
      void send({ kind: expects === "trace" ? "trace" : "tap", answer: value });
    },
    [directive, send]
  );

  /** The child pressed the microphone themselves rather than waiting. */
  const speakAnswer = useCallback(async () => {
    const current = directive;
    if (!current || listening) return;
    setListening(true);
    const heard = await captureClassSpeech({
      expect: current.listen.expect,
      contextualStrings:
        current.listen.contextual_strings.length > 0
          ? current.listen.contextual_strings
          : current.scaffold.options_shown,
      language: current.listen.language,
      timeoutMs: current.listen.hold_open_ms || current.next_input.timeout_ms
    });
    if (mounted.current) setListening(false);
    if (!heard.transcript) return;
    await send({
      kind: "voice",
      answer: heard.transcript,
      confidence: heard.confidence,
      alternatives: heard.alternatives
    });
  }, [directive, listening, send]);

  /** Say the current line again. Changes nothing on the server. */
  const repeat = useCallback(async () => {
    if (directive?.speech.text) await speakTextAsync(directive.speech.text);
  }, [directive]);

  /** Hand raised. The server pauses the class and keeps the place. */
  const raiseHand = useCallback(() => {
    void send({ kind: "doubt" });
  }, [send]);

  return {
    directive,
    loading,
    busy,
    error,
    notToday,
    listening,
    phase: directive?.phase ?? null,
    answer,
    speakAnswer,
    repeat,
    raiseHand,
    clearError: () => setError("")
  };
}
