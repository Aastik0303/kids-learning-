import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/services/api/client";
import { teacherApi } from "@/services/api/teacherApi";
import { track } from "@/services/analytics/analytics";
import { haptics } from "@/services/audio/haptics";
import { voiceController } from "@/features/voice/VoiceController";
import { announcePlanChanged } from "@/features/plan/useTodayPlan";
import {
  EXAMPLE_HOLD_MS,
  MS_PER_WORD,
  findSpokenExamples,
  type SpokenExample,
} from "@/lib/spokenExamples";
import { useAudioStore } from "@/store/audioStore";
import { useChildStore } from "@/store/childStore";
import type { TeacherTurn } from "@/types/teacher";

/**
 * Drives one sitting of the AI Teacher - which is the class.
 *
 * The shape is the same loop the web runs, because it is the same class:
 *
 *   1. say the feedback, then the teaching, then the question, then the cue to
 *      speak - the order a person says them in;
 *   2. if the question wants a spoken answer, open the microphone by itself. A
 *      four-year-old should never have to know that a button means "now talk";
 *   3. send what came back, and render the turn that answers it.
 *
 * What this hook does **not** do is decide anything. Not whether an answer was
 * right, not what comes next, not how many questions a stage has, not when the
 * day ends. All of that is the server's, marked in plain Python from the
 * author's own key, which matters because the verdict pays stars.
 *
 * The one thing it decides is *when to carry on by itself*, and even that is
 * bounded: the ten-second clock may not start until the explanation has
 * actually been heard. A child who has understood should not have to find a
 * button, and a class that moves on over an explanation nobody heard is worse
 * than one that waits.
 */

/** How long the explaining step waits before carrying on by itself. */
const AUTO_NEXT_MS = 10_000;

/** Said after the question, so the child knows the microphone is theirs now. */
export const SPEAK_NOW = "Say it out loud!";

/**
 * How long the panda wears the verdict on its face.
 *
 * Long enough for a small child to look up and see it, short enough that it is
 * not still celebrating over the question after it. It runs from the moment the
 * marked turn arrives, alongside the narration rather than after it: "Well
 * done!" is under a second of audio, and the delight used to be over before a
 * three-year-old had lifted their eyes off their own finger.
 */
const REACTION_MS = 2600;

/**
 * How long the line just shown *should* have taken to say.
 *
 * Normally the end of the narration is known exactly - the speak promise
 * resolves when the audio does - but there are ordinary ways for the voice not
 * to play at all: the sound muted, no speech engine, a backend that is not
 * answering. In every one of those the promise resolves in a few milliseconds,
 * and without a floor the ten-second clock would start on an explanation nobody
 * has heard *or* had time to read. Roughly two words a second, which is a slow,
 * four-year-old-facing pace, plus a moment to look at the picture.
 */
export function readingMs(line: string): number {
  const words = line.trim().split(/\s+/).filter(Boolean).length;
  if (!words) return 0;
  return Math.min(30_000, 800 + Math.round((words / 2) * 1000));
}

export type MicTrouble = "" | "blocked" | "silence" | "unsupported";

export function useAiTeacherClass() {
  const child = useChildStore((state) => state.activeChild);
  const refreshChild = useChildStore((state) => state.refresh);

  const [turn, setTurn] = useState<TeacherTurn | null>(null);
  const [busy, setBusy] = useState(true);
  const [listening, setListening] = useState(false);
  const [reacting, setReacting] = useState(false);
  const [error, setError] = useState("");
  const [micNote, setMicNote] = useState<MicTrouble>("");
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  /**
   * The example the teacher is saying *right now*, on the board in place of the
   * thing being taught.
   *
   * An explaining turn always reaches for something the child has seen - "A is
   * for apple", "round like a ball" - and a child who cannot read hears that
   * word with nothing to look at, because the board is holding the letter. So
   * the letter steps aside for three seconds while the example is up, and then
   * comes back. `findSpokenExamples` decides which words those are and when;
   * this only holds the one that is showing.
   */
  const [example, setExample] = useState<SpokenExample | null>(null);
  const exampleTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const speaking = useAudioStore((state) => state.isSpeaking);

  const mounted = useRef(true);
  /**
   * Bumped by every new turn and every question the child asks, so a timer or
   * an open microphone from a previous beat can never move a lesson the child
   * is already busy with.
   */
  const beat = useRef(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  /**
   * Whether a recogniser is open right now, in a ref rather than in state.
   * State is not enough: tapping the microphone mid-explanation stops the
   * speech, which resolves the promise the turn is awaiting, so both callers
   * would see `listening === false` and open two recognisers.
   */
  const listeningRef = useRef(false);
  /** The end of the narration, or when it would have been. */
  const narrationEndsAt = useRef<number | null>(null);
  const [narrationTick, setNarrationTick] = useState(0);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  /**
   * Take every example off the board and cancel the ones still queued.
   *
   * Called wherever the narration stops early - the microphone opening, a
   * question being asked, a new turn arriving, the screen going away - because
   * a schedule built for a sentence that is no longer being said would put a
   * picture up over the next thing the child is looking at.
   */
  const clearExamples = useCallback(() => {
    exampleTimers.current.forEach(clearTimeout);
    exampleTimers.current = [];
    setExample(null);
  }, []);

  /**
   * Put each example up as its word comes round, and take it down three
   * seconds later.
   *
   * The hold is per example rather than one shared "hide" timer, which is safe
   * because `findSpokenExamples` refuses to place two inside one hold -
   * otherwise the first one's exit would take the second one down with it.
   */
  const playExamples = useCallback(
    (cues: SpokenExample[]) => {
      clearExamples();
      cues.forEach((cue) => {
        exampleTimers.current.push(
          setTimeout(() => {
            if (mounted.current) setExample(cue);
          }, cue.atMs),
        );
        exampleTimers.current.push(
          setTimeout(() => {
            // Only clears itself. A later example that has already taken the
            // board must not be wiped by an earlier one's timer.
            if (mounted.current) setExample((shown) => (shown === cue ? null : shown));
          }, cue.atMs + EXAMPLE_HOLD_MS),
        );
      });
    },
    [clearExamples],
  );

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      beat.current += 1;
      clearTimers();
      clearExamples();
      void voiceController.stopAll();
    };
  }, [clearTimers, clearExamples]);

  /**
   * A level has been finished, so the copies of the child's progress that other
   * screens read are now behind.
   *
   * The stars, the completed level and the unlock all happened on the server;
   * the stored profile is a snapshot from before this stage. Without this the
   * header still shows the old star count, the schedule strip still shows the
   * level that was current a moment ago, and the Adventure board still draws
   * the level that has just opened as asleep.
   */
  const refreshProgress = useCallback(() => {
    void refreshChild();
    announcePlanChanged();
  }, [refreshChild]);

  const sendRef = useRef<((answer: string) => Promise<void>) | null>(null);
  const listenRef = useRef<(() => Promise<void>) | null>(null);

  /** Render one turn: say it, then collect whatever it asks for. */
  const show = useCallback(async (next: TeacherTurn) => {
    beat.current += 1;
    const mine = beat.current;
    clearTimers();
    setTurn(next);
    setMicNote("");
    narrationEndsAt.current = null;
    setNarrationTick((tick) => tick + 1);

    const wantsVoice =
      Boolean(next.question) &&
      next.expects !== "ready" &&
      next.expects !== "trace" &&
      next.expects !== "done";

    const line = [next.feedback, next.speech, next.question, wantsVoice ? SPEAK_NOW : ""]
      .filter(Boolean)
      .join(" ");

    // The examples ride along with the narration. Only the *explanation* is
    // searched - not the feedback before it and not the question after it -
    // because an example is a thing the teacher reaches for while explaining,
    // and the question is the moment the concept itself has to be on the board.
    // The options are handed over as words never to illustrate: on a match or a
    // quiz the teacher says the answer's name on the way into the question, and
    // a picture of it is the answer given away. So are `not_examples` - the
    // everyday things belonging to this concept's siblings, which an
    // explanation reaches for as a contrast ("three corners, not round like a
    // ball") and which the web class was drawing: the circle's ball on the
    // triangle's card.
    playExamples(
      findSpokenExamples(next.speech ?? "", {
        wordsBefore: (next.feedback ?? "").split(/\s+/).filter(Boolean).length,
        skip: [next.visual_value, ...(next.options ?? []), ...(next.not_examples ?? [])],
        msPerWord: MS_PER_WORD,
      }),
    );

    const startedAt = Date.now();
    // Deliberately no language argument. The narration is English in every
    // subject, the Hindi ones included - there Hindi is the *content*, quoted
    // in Devanagari inside an English sentence - and `tts` switches voices for
    // the Devanagari runs by itself.
    await voiceController.speak(line);
    if (!mounted.current || mine !== beat.current) return;

    // When the voice really played, that is the end of the narration. When it
    // came back far too fast to have said anything, the reading floor is used
    // instead, so the explanation still gets time on the screen. Trusting the
    // audio when it did play matters: the floor is a slow estimate and adding
    // it on top of a narration that has already finished would leave a child
    // sitting in front of a finished sentence for several seconds.
    const elapsed = Date.now() - startedAt;
    const floor = readingMs(line);
    narrationEndsAt.current = elapsed >= floor / 2 ? Date.now() : startedAt + floor;
    setNarrationTick((tick) => tick + 1);
    // Whatever is left queued belongs to a sentence that has finished.
    clearExamples();

    if (wantsVoice) await listenRef.current?.();
  }, [clearTimers, playExamples, clearExamples]);

  const send = useCallback(
    async (answer: string) => {
      const current = turn;
      if (!current || !answer.trim() || busy) return;
      setBusy(true);
      setError("");
      try {
        const next = await teacherApi.answer(current.session_id, answer.trim());
        if (!mounted.current) return;
        setBusy(false);
        if (next.topic_completed || next.day_complete) refreshProgress();
        void show(next);
      } catch (caught) {
        if (!mounted.current) return;
        setBusy(false);
        setError(caught instanceof ApiError ? caught.childMessage : "Let us try that again!");
      }
    },
    [turn, busy, refreshProgress, show],
  );

  sendRef.current = send;

  /**
   * Open the microphone and answer with what was heard.
   *
   * Every outcome is reported. Ending this at `if (transcript) send(...)` makes
   * a denied permission, a device that cannot listen and a child who said
   * nothing all the same thing on screen - nothing at all - and there is no way
   * to tell those apart from the outside, nor to fix any of them if the app
   * will not say which one happened.
   */
  const speakAnswer = useCallback(async () => {
    const current = turn;
    if (!current || listeningRef.current || busy) return;
    listeningRef.current = true;

    // The teacher may still be talking, and the recogniser would hear the tail
    // of its own voice. Stopping first is also what makes a tap on the
    // microphone interrupt the explanation rather than queue behind it.
    await voiceController.stopSpeaking();
    // The examples were timed to a sentence that is no longer being said.
    clearExamples();
    setMicNote("");
    setListening(true);

    const heard = await voiceController.listenForDirective({
      // The options are handed to the recogniser as the words to expect: a
      // child saying "triangle" is far likelier to come back as "triangle" when
      // the device has been told that is a word in play.
      contextualStrings: [...(current.options ?? []), current.topic_title].filter(Boolean),
      expect: current.question,
      timeoutMs: 8000,
    });

    listeningRef.current = false;
    if (!mounted.current) return;
    setListening(false);

    if (heard.outcome === "permission_denied") {
      setMicNote("blocked");
      return;
    }
    if (heard.outcome === "unavailable") {
      setMicNote("unsupported");
      return;
    }
    if (!heard.transcript.trim()) {
      setMicNote("silence");
      return;
    }
    await sendRef.current?.(heard.transcript);
  }, [turn, busy, clearExamples]);

  listenRef.current = speakAnswer;

  /**
   * The child asked something of their own accord. The teacher answers from its
   * notes and the lesson stays exactly where it was - including the ten-second
   * clock, which starts again so nobody is hurried out of a conversation.
   */
  const askSomething = useCallback(async () => {
    const current = turn;
    if (!current || listeningRef.current || busy) return;
    listeningRef.current = true;
    // Interrupting the teacher to ask something is the whole point of this
    // button, so it stops the talking rather than refusing while it goes on.
    await voiceController.stopSpeaking();
    clearExamples();
    setMicNote("");
    setListening(true);

    const heard = await voiceController.listenForDirective({
      contextualStrings: [current.topic_title],
      // A question takes longer to say than an answer.
      timeoutMs: 10000,
    });

    listeningRef.current = false;
    if (!mounted.current) return;
    setListening(false);

    if (heard.outcome === "permission_denied") {
      setMicNote("blocked");
      return;
    }
    if (!heard.transcript.trim()) {
      setMicNote("silence");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const answered = await teacherApi.ask(current.session_id, heard.transcript);
      if (!mounted.current) return;
      setBusy(false);
      void show(answered);
    } catch (caught) {
      if (!mounted.current) return;
      setBusy(false);
      setError(caught instanceof ApiError ? caught.childMessage : "Let us try that again!");
    }
  }, [turn, busy, show, clearExamples]);

  /** Say the current line again. Changes nothing on the server. */
  const repeat = useCallback(async () => {
    const current = turn;
    if (!current) return;
    await voiceController.speak([current.speech, current.question].filter(Boolean).join(" "));
  }, [turn]);

  /** A tapped answer, or the "ready" that carries an explanation on. */
  const answer = useCallback(
    (value: string) => {
      haptics.tap();
      void sendRef.current?.(value);
    },
    [],
  );

  // ── Opening the class ────────────────────────────────────────────────
  useEffect(() => {
    if (!child) return;
    let cancelled = false;
    setBusy(true);
    setError("");

    // Ask for the microphone on the way in rather than in the middle of the
    // first question. Waking the audio device is most of the delay between the
    // teacher finishing a question and the recogniser actually hearing
    // anything, and a permission sheet that appears *over* a question is a
    // question the child never sees.
    void voiceController.ensurePermission();

    teacherApi
      .open(child.child_id)
      .then((first) => {
        if (cancelled || !mounted.current) return;
        setBusy(false);
        track("teacher_opened", { topic_id: first.topic_id, stage: first.stage });
        void show(first);
      })
      .catch((caught: unknown) => {
        if (cancelled || !mounted.current) return;
        setBusy(false);
        setError(
          caught instanceof ApiError
            ? caught.childMessage
            : "We could not open your class. Let us try again!",
        );
      });

    return () => {
      cancelled = true;
    };
    // Opening is keyed on the child alone; `show` is stable enough that
    // including it would reopen the class on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [child?.child_id]);

  // ── Carrying on by itself, once the explanation has been heard ────────
  useEffect(() => {
    const endsAt = narrationEndsAt.current;
    if (
      !turn ||
      turn.expects !== "ready" ||
      turn.day_complete ||
      busy ||
      speaking ||
      listening ||
      endsAt === null
    ) {
      setSecondsLeft(null);
      return;
    }

    const mine = beat.current;
    // The deadline is computed from the wall clock rather than counted down in
    // ticks, so an app that was in the background does not come back with eight
    // seconds still on a clock that should have finished long ago.
    const deadline = Math.max(endsAt, Date.now()) + AUTO_NEXT_MS;
    const render = () => {
      if (!mounted.current || mine !== beat.current) return;
      const remaining = deadline - Date.now();
      setSecondsLeft(Math.max(0, Math.ceil(remaining / 1000)));
      if (remaining <= 0) {
        clearInterval(tick);
        void sendRef.current?.("ready");
      }
    };
    render();
    const tick = setInterval(render, 250);
    return () => clearInterval(tick);
  }, [turn, busy, speaking, listening, narrationTick]);

  // ── The verdict, worn for a moment ───────────────────────────────────
  useEffect(() => {
    if (turn?.is_correct !== true && turn?.is_correct !== false) {
      setReacting(false);
      return;
    }
    setReacting(true);
    const timer = setTimeout(() => {
      if (mounted.current) setReacting(false);
    }, REACTION_MS);
    return () => clearTimeout(timer);
  }, [turn]);

  return {
    turn,
    example,
    busy,
    speaking,
    listening,
    reacting,
    error,
    micNote,
    secondsLeft,
    answer,
    speakAnswer,
    askSomething,
    repeat,
    clearError: () => setError(""),
  };
}
