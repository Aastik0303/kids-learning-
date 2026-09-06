"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { AIAvatar } from "@/components/avatar/AIAvatar";
import { avatarStateForTeacher } from "@/components/avatar/avatar.config";
import { AnswerChoice } from "@/components/curriculum/AnswerChoice";
import { AppShell } from "@/components/shared/AppShell";
import { Blackboard } from "@/components/blackboard/Blackboard";
import { TraceCanvas } from "@/components/learning/TraceCanvas";
import { NoChildNotice } from "@/components/shared/NoChildNotice";
import { announcePlanChanged } from "@/lib/useTodayPlan";
import { useActiveChild } from "@/lib/useActiveChild";
import { getProgress } from "@/services/child";
import { saveChild } from "@/services/session";
import { answerTeacher, askTeacher, openTeacher, type TeacherTurn } from "@/services/aiTeacher";
import { canUseSpeechRecognition, captureClassSpeech, speakTextAsync, stopSpeech } from "@/services/speech";
import { primeMicrophone, releaseMicrophone, SPEECH_LEVEL } from "@/services/micStream";

/**
 * Why the microphone did not produce an answer, in words a grown-up can act on.
 *
 * Every one of these used to be the same thing on screen: nothing. The mic
 * opened, the child spoke, and the page silently did not move — which is
 * indistinguishable from the app being broken, and is what "the mic is not
 * taking my response" actually looks like from the other side.
 */
const MIC_TROUBLE = {
  blocked:
    "The microphone is blocked. Click the padlock in the address bar, allow the microphone, then reload.",
  insecure:
    "The microphone only works on localhost or https. Open the app at http://localhost:5000 rather than by IP address.",
  unsupported: "This browser cannot listen. Use Chrome or Edge, or type the answer below.",
  silence: "I did not hear anything. Tap the microphone and try again, or type the answer below."
} as const;

/**
 * The AI Teacher — the class.
 *
 * The bot retrieves from the project's own teaching notes, explains in one of
 * nine strategies, and asks five questions — and a stage is one level out of
 * today's frozen plan. Finishing one marks that level done on the Adventure map
 * and unlocks the next; finishing the last one ends the day, and the class will
 * not reopen until tomorrow.
 *
 * Every question gets three turns: it is asked, then asked again with a hint —
 * a deeper explanation and two or three things to choose between — and then, if
 * it still has not come, the answer is told and explained and the class moves
 * on. The third turn is not a test and carries no mark.
 *
 * **There is no score on this screen.** There is no number that goes up when the
 * child is right and down when they are not, because a four-year-old who is
 * still learning what a letter *is* should be watching the letter. What is drawn
 * instead is where they are: which question of the five, and which level of the
 * day.
 *
 * Nothing on this screen decides any of that. The server sends `stage` of
 * `stages_total`, and `day_complete` with `expects: "done"` when the day is
 * over; this page renders what it is told, which is what stops a reload being a
 * way back into a day that is finished.
 *
 * The avatar stands in the middle and does the talking, which is the whole
 * shape of this screen: one character, centred, speaking, with the question
 * underneath it. There is no second avatar — the corner dock is hidden here.
 */
/** What each step is called on screen, for the grown-up reading along. */
/**
 * How long the explaining step waits before carrying on by itself.
 *
 * A child who has understood should not have to find a button, and one who
 * wants to ask something should not be rushed - so asking restarts the clock
 * rather than running beside it.
 */
const AUTO_NEXT_MS = 10_000;

/** Said after the question, so the child knows the microphone is theirs now. */
const SPEAK_NOW = "Say it out loud!";

/**
 * How long the line just shown *should* have taken to say.
 *
 * The countdown to the next step may only begin once the child has actually
 * heard the explanation. Normally that is known exactly - the narration promise
 * resolves when the audio ends - but there are several ordinary ways for the
 * voice not to play at all: autoplay refused until the page is tapped, the
 * backend not running, a device with no speech at all. In every one of those
 * the promise resolves in a few milliseconds, and before this the ten-second
 * clock started immediately and moved the class on from an explanation nobody
 * had heard *or* had time to read.
 *
 * So when the voice comes back suspiciously fast, the clock still waits out a
 * floor derived from the length of the line. Roughly two words a second, which
 * is a slow, four-year-old-facing pace, plus a moment to look at the picture.
 */
function readingMs(line: string): number {
  const words = line.trim().split(/\s+/).filter(Boolean).length;
  if (!words) return 0;
  return Math.min(30_000, 800 + Math.round((words / 2) * 1000));
}

const STEP_LABELS: Record<string, string> = {
  explain: "👂 Listen",
  say_it: "🗣️ Say it",
  draw: "✏️ Draw it",
  match: "👀 Find it",
  quiz: "🧠 One more",
  /**
   * The check-in the schedule opens the class with: something taught two days
   * ago, asked again with a different question. It is not part of the lesson —
   * nothing about answering it is marked, counted or allowed near a star — so
   * it is named for what it is rather than as a step of the level.
   */
  retention: "🧩 Remember"
};

/**
 * What the two helping turns are called on screen.
 *
 * Both are named for what the teacher is doing, never for what the child did:
 * "here is a hint" and "here is the answer", not "wrong again". A child who has
 * missed the same thing twice does not need it counted for them.
 */
/**
 * Where the bar has to reach before somebody is audible.
 *
 * `showLevel` draws a quarter of full scale as a full bar, because a child two
 * feet from a laptop microphone never gets anywhere near 1.0 and a bar that
 * barely twitches reads as "it cannot hear me" - so the speech floor is scaled
 * the same way.
 */
const LEVEL_SCALE = 4;
const HEARD_LEVEL = SPEECH_LEVEL * LEVEL_SCALE;

const HINT_LABEL = "💡 Here is a hint";
const REVEAL_LABEL = "🔑 Here is the answer";

export default function AiTeacherPage() {
  const { child, status, error: childError } = useActiveChild();
  const [turn, setTurn] = useState<TeacherTurn | null>(null);
  const [busy, setBusy] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState("");
  // Whether this browser can listen at all. Read after mount, never during
  // render: `canUseSpeechRecognition()` looks at `window`, which the server does
  // not have, so asking during render makes the server say "no microphone" and
  // the browser say "yes" - and React throws the whole tree away and rebuilds it.
  const [canListen, setCanListen] = useState(false);
  // What went wrong with the microphone last time, if anything. Kept apart from
  // `error` (which is about the server) so a mic problem does not look like the
  // lesson failing, and so it can sit next to the mic where it is useful.
  const [micNote, setMicNote] = useState("");
  // How loud the room is while the microphone is open, 0…1. Drawn as a bar so a
  // child can see that a quiet voice is being picked up, instead of learning to
  // shout at a circle that looks the same either way.
  const [micLevel, setMicLevel] = useState(0);
  const micBucket = useRef(-1);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  // The moment this turn's narration finished, or - when the voice never
  // played - the moment it would have. Null while it is still being said, which
  // is what keeps the auto-advance clock from starting during the explanation.
  const [narrationEndsAt, setNarrationEndsAt] = useState<number | null>(null);
  const mounted = useRef(true);
  // Whether a recogniser is open right now, tracked in a ref rather than in
  // `listening` state.
  //
  // State is not enough here. Tapping the mic mid-explanation calls
  // `stopSpeech()`, which resolves the promise `show()` is awaiting, so `show()`
  // immediately runs its own "now listen" step — before React has re-rendered
  // with `listening: true`. Both callers then see `listening === false` and
  // start a second recogniser, the browser refuses it, and the child is told "I
  // did not hear anything" while the first one is still listening to them.
  const listeningRef = useRef(false);
  // Bumped by every new turn and every question the child asks, so a timer from
  // a previous beat can never move a lesson the child is still busy with.
  const beat = useRef(0);

  useEffect(() => {
    mounted.current = true;
    const supported = canUseSpeechRecognition();
    setCanListen(supported);
    // Chrome refuses the microphone outright on a page that is neither https nor
    // localhost — and it refuses it *silently*. Opening the app by LAN IP to try
    // it on a tablet is the usual way to land here, so say so up front rather
    // than letting somebody tap a dead button.
    if (!supported) {
      setMicNote(MIC_TROUBLE.unsupported);
    } else if (typeof window !== "undefined" && !window.isSecureContext) {
      setMicNote(MIC_TROUBLE.insecure);
    }
    // Open the microphone once, on the way into the class, and keep it open for
    // as long as the class is on screen. Waking the audio device is most of the
    // delay between tapping the mic and it actually hearing anything, and it is
    // paid here - before the first question - instead of at every answer. A
    // refused microphone resolves quietly; the buttons say so themselves.
    void primeMicrophone();
    return () => {
      mounted.current = false;
      stopSpeech();
      releaseMicrophone();
    };
  }, []);

  /**
   * The level, quantised.
   *
   * It arrives sixteen times a second and a bar this size has about ten
   * distinguishable steps, so anything finer is re-rendering the page for a
   * change nobody can see.
   */
  const showLevel = useCallback((level: number) => {
    const bucket = Math.min(10, Math.round(level * LEVEL_SCALE * 10));
    if (bucket === micBucket.current) return;
    micBucket.current = bucket;
    if (mounted.current) setMicLevel(bucket / 10);
  }, []);

  const say = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setSpeaking(true);
    await speakTextAsync(text);
    if (mounted.current) setSpeaking(false);
  }, []);

  const listenRef = useRef<(() => Promise<void>) | null>(null);

  const show = useCallback(
    async (next: TeacherTurn) => {
      beat.current += 1;
      const mine = beat.current;
      setTurn(next);
      setTyped("");
      setMicNote("");
      // Feedback about the last answer first, then the new teaching, then the
      // question, and last the cue to speak — the order a person says them in.
      // The microphone opens straight afterwards, so a child never has to know
      // that a button means "now talk".
      const wantsVoice =
        Boolean(next.question) &&
        next.expects !== "ready" &&
        next.expects !== "trace" &&
        next.expects !== "done";
      const line = [next.feedback, next.speech, next.question, wantsVoice ? SPEAK_NOW : ""]
        .filter(Boolean)
        .join(" ");
      // A new turn is never immediately skippable: the clock is cleared here and
      // only set again once the line has been said.
      setNarrationEndsAt(null);
      const startedAt = Date.now();
      await say(line);
      if (!mounted.current || mine !== beat.current) return;
      // When the voice really played, that is the end of the narration and the
      // clock starts now. When it came back far too fast to have said anything -
      // autoplay refused, no backend, a device with no speech - the floor is
      // used instead, so the explanation still gets time on the screen. Trusting
      // the audio when it did play matters: the floor is a slow estimate, and
      // adding it on top of a narration that already finished would leave a
      // child sitting in front of a finished sentence for several seconds.
      const elapsed = Date.now() - startedAt;
      const floor = readingMs(line);
      setNarrationEndsAt(elapsed >= floor / 2 ? Date.now() : startedAt + floor);
      if (wantsVoice) await listenRef.current?.();
    },
    [say]
  );

  useEffect(() => {
    if (!child) return;
    let cancelled = false;
    setBusy(true);
    openTeacher(child.child_id)
      .then((first) => {
        if (cancelled || !mounted.current) return;
        setBusy(false);
        void show(first);
      })
      .catch((err: unknown) => {
        if (cancelled || !mounted.current) return;
        setBusy(false);
        setError(err instanceof Error ? err.message : "The AI Teacher could not start.");
      });
    return () => {
      cancelled = true;
    };
  }, [child, show]);

  /**
   * A level has been finished, so the copies of the child's progress that other
   * screens read are now behind.
   *
   * The stars, the completed level and the unlock all happened on the server.
   * The stored profile is a snapshot from before this stage, so without this the
   * header still shows the old star count, the schedule strip still shows the
   * level that was current a moment ago, and the Adventure map still draws the
   * level that has just opened as asleep.
   */
  const refreshProgress = useCallback(() => {
    if (!child) return;
    getProgress(child.child_id)
      .then((refreshed) => {
        saveChild(refreshed.child);
        announcePlanChanged();
      })
      // A stale star count is not worth breaking the lesson over.
      .catch(() => undefined);
  }, [child]);

  async function send(answer: string) {
    const current = turn;
    if (!current || !answer.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const next = await answerTeacher(current.session_id, answer.trim());
      if (!mounted.current) return;
      setBusy(false);
      if (next.topic_completed || next.day_complete) refreshProgress();
      void show(next);
    } catch (err: unknown) {
      if (!mounted.current) return;
      setBusy(false);
      setError(err instanceof Error ? err.message : "Let us try that again.");
    }
  }

  listenRef.current = speakAnswer;

  /**
   * Open the microphone and answer with what was heard.
   *
   * Every outcome is reported. It used to end `if (heard.transcript) send(...)`,
   * so a denied permission, a browser that cannot listen and a child who said
   * nothing were all the same thing on screen — nothing at all. There is no way
   * to tell those apart from the outside, and no way to fix any of them if the
   * app will not say which one happened.
   */
  async function speakAnswer() {
    if (!turn || listeningRef.current || busy) return;
    listeningRef.current = true;

    // The guide may still be talking, and the recogniser would hear the tail of
    // its own voice. Stopping first is also what makes a second tap on the mic
    // interrupt the explanation rather than queue behind it.
    stopSpeech();
    setSpeaking(false);

    setMicNote("");
    setListening(true);
    // The options are handed to the recogniser as the words it should expect:
    // a child saying "triangle" is much likelier to come back as "triangle"
    // when the browser has been told that is a word in play.
    const heard = await captureClassSpeech({
      expect: "",
      contextualStrings: [...(turn.options ?? []), turn.topic_title],
      timeoutMs: 8000,
      onLevel: showLevel
    });
    listeningRef.current = false;
    if (!mounted.current) return;
    setListening(false);

    if (heard.blocked) {
      setMicNote(MIC_TROUBLE.blocked);
      return;
    }
    if (!heard.transcript) {
      setMicNote(MIC_TROUBLE.silence);
      return;
    }
    await send(heard.transcript);
  }

  /**
   * The child asked something of their own. The bot answers from its notes and
   * the lesson stays exactly where it was — including the ten-second clock,
   * which starts again so nobody is hurried out of a conversation.
   */
  async function askSomething() {
    const current = turn;
    if (!current || listeningRef.current || busy) return;
    listeningRef.current = true;
    // Interrupting the guide to ask something is the whole point of this button,
    // so it stops the talking rather than refusing while it is going on.
    stopSpeech();
    setSpeaking(false);
    setMicNote("");
    setListening(true);
    const heard = await captureClassSpeech({
      expect: "",
      contextualStrings: [current.topic_title],
      // A question takes longer to say than an answer.
      timeoutMs: 10000,
      onLevel: showLevel
    });
    listeningRef.current = false;
    if (!mounted.current) return;
    setListening(false);
    if (heard.blocked) {
      setMicNote(MIC_TROUBLE.blocked);
      return;
    }
    if (!heard.transcript) {
      setMicNote(MIC_TROUBLE.silence);
      return;
    }

    setBusy(true);
    setError("");
    try {
      const answered = await askTeacher(current.session_id, heard.transcript);
      if (!mounted.current) return;
      setBusy(false);
      void show(answered);
    } catch (err: unknown) {
      if (!mounted.current) return;
      setBusy(false);
      setError(err instanceof Error ? err.message : "Let us try that again.");
    }
  }

  /**
   * Carrying on by itself, once the explanation has actually been heard.
   *
   * The button exists, but a two- or three-year-old cannot be relied on to
   * press it, so the class has to move on on its own. What it must not do is
   * move on *over* the explanation, which is what happened whenever the voice
   * did not play: the clock started the instant the turn arrived.
   *
   * It now starts from `narrationEndsAt` - the end of the audio, or the reading
   * floor when there was no audio - and the deadline is computed from the wall
   * clock rather than counted down in ticks, so a tab that was backgrounded
   * (where browsers throttle timers to once a minute) does not come back with
   * eight seconds still on a clock that should have finished long ago.
   */
  useEffect(() => {
    if (
      !turn ||
      turn.expects !== "ready" ||
      turn.day_complete ||
      busy ||
      speaking ||
      listening ||
      narrationEndsAt === null
    ) {
      setSecondsLeft(null);
      return;
    }
    const mine = beat.current;
    const deadline = Math.max(narrationEndsAt, Date.now()) + AUTO_NEXT_MS;
    // Declared before `render` reads it: the first call happens synchronously,
    // below, and a `const` here would be in its temporal dead zone.
    let tick = 0;
    const render = () => {
      if (!mounted.current || mine !== beat.current) return;
      const remaining = deadline - Date.now();
      setSecondsLeft(Math.max(0, Math.ceil(remaining / 1000)));
      if (remaining <= 0) {
        window.clearInterval(tick);
        void send("ready");
      }
    };
    render();
    tick = window.setInterval(render, 250);
    return () => window.clearInterval(tick);
    // `send` is stable enough that including it would restart the clock on
    // every render, which is the one thing this must not do.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turn, busy, speaking, listening, narrationEndsAt]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(typed);
  }

  if (status !== "loading" && status !== "ready") {
    return (
      <AppShell>
        <NoChildNotice status={status} error={childError} />
      </AppShell>
    );
  }

  const stages = turn?.stages_total || 1;
  // How far through this level's five questions the child is. Progress, not a
  // score: it only ever goes up, and a question the teacher had to answer counts
  // the same as one the child got.
  const perStage = turn?.questions_per_stage ?? 5;
  const done = Math.min(turn?.questions_asked ?? 0, perStage);
  // The whole day is through. The server said so; this screen only obeys it.
  const dayDone = Boolean(turn?.day_complete);
  // The turn that gives the answer away. Nothing here is being tested.
  const revealing = Boolean(turn?.is_reveal);
  /**
   * What tells the blackboard that this is a new turn and it should be wiped.
   *
   * Every part of a turn that changes what is drawn is in it, the attempt
   * included: a question asked again with a hint draws its picture again rather
   * than leaving the finished one from the first ask sitting there. Two turns
   * that really do draw the same thing keep the same key and the board is left
   * alone, which is what stops a re-render from restarting the chalk.
   */
  /**
   * What the panda's face is doing.
   *
   * It reacts while the feedback is being said and settles into waiting once
   * the talking stops - a face that stayed delighted through the next question
   * would be grinning at a child who is stuck on it. A wrong answer makes it
   * *kind*, never sad; sad is only for the app's own failures, which here means
   * the microphone that heard nothing and the server that did not answer.
   */
  const mood = avatarStateForTeacher({
    speaking,
    listening,
    waiting: busy,
    sorry: Boolean(error) || micNote === MIC_TROUBLE.silence,
    turn
  });

  const boardKey = [
    turn?.session_id ?? "none",
    turn?.topic_id ?? "",
    turn?.step ?? "",
    turn?.step_index ?? 0,
    turn?.questions_asked ?? 0,
    turn?.attempt ?? 1,
    turn?.visual_kind ?? "",
    turn?.visual_value ?? ""
  ].join("|");

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="surface-panel flex flex-wrap items-center justify-between gap-3 rounded-[2rem] p-5">
          <div>
            <p className="text-sm font-black uppercase tracking-wide text-sky">
              🧑‍🏫 Today&apos;s class
            </p>
            <h1 className="text-3xl font-black text-ink sm:text-4xl">
              {dayDone ? "All done for today!" : (turn?.topic_title ?? "Today's lesson")}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-lg font-black text-ink">
            {/* A stage is a level out of today's plan, so this is where in the
                *day* the child is — not a difficulty they have climbed to. */}
            <span className="rounded-full bg-white px-4 py-2 shadow-soft">
              🎯 Level {turn?.stage ?? 1} of {stages}
            </span>
            {/* The five questions, as five dots. A pre-reader cannot read "3 of
                5", and a filled dot is the same fact without a number in it. */}
            {dayDone ? null : (
              <span
                className="flex items-center gap-2 rounded-full bg-white px-4 py-2 shadow-soft"
                aria-label={`Question ${Math.min(done + 1, perStage)} of ${perStage}`}
                data-testid="question-dots"
              >
                {Array.from({ length: perStage }, (_, index) => (
                  <span
                    key={index}
                    aria-hidden
                    className={`h-4 w-4 rounded-full ${
                      index < done ? "bg-leaf" : "bg-ink/15"
                    }`}
                  />
                ))}
              </span>
            )}
          </div>
        </div>

        {/* Where the lesson is inside this one concept. */}
        {turn?.step && !dayDone ? (
          <p className="text-center text-sm font-black uppercase tracking-wide text-ink/40">
            {STEP_LABELS[turn.step] ?? turn.step} · step {(turn.step_index ?? 0) + 1} of{" "}
            {turn.steps_total ?? 5}
          </p>
        ) : null}

        {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}

        {/* The teacher, centre stage. */}
        <div className="surface-panel grid justify-items-center gap-5 rounded-[2rem] p-6 text-center">
          <div
            className={`h-56 w-56 transition-transform ${
              mood === "celebrating" || mood === "proud"
                ? "scale-110"
                : speaking
                  ? "scale-105"
                  : "scale-100"
            }`}
            aria-hidden
          >
            <AIAvatar state={mood} effect={null} isSpeaking={speaking} />
          </div>

          {/* A level finished. This is the only place the Adventure map ever
              moves from, so it is worth the child seeing it happen. */}
          {turn?.topic_completed ? (
            <p
              data-testid="level-complete"
              className="rounded-full bg-leaf/15 px-5 py-2 text-lg font-black text-leaf"
            >
              🎉 Level finished
              {turn.stars_earned ? ` · ⭐ ${turn.stars_earned}` : ""}
              {turn.next_topic_unlocked ? " · a new level opened on your map" : ""}
            </p>
          ) : null}

          {/* What the teacher said about the last answer. Warm either way, and
              with no number after it — there is nothing to add up. */}
          {turn?.feedback ? (
            <p
              className={`rounded-full px-5 py-2 text-lg font-black ${
                turn.is_correct ? "bg-leaf/15 text-leaf" : "bg-sunshine/40 text-ink"
              }`}
            >
              {turn.feedback}
            </p>
          ) : null}

          {/* Which of the question's three turns this is, when it is not the
              first. Named for what the teacher is doing, never for what the
              child did. */}
          {turn?.is_hint || revealing ? (
            <p
              data-testid={revealing ? "reveal" : "hint"}
              className={`rounded-full px-5 py-2 text-lg font-black ${
                revealing ? "bg-sky/15 text-sky" : "bg-sunshine/40 text-ink"
              }`}
            >
              {revealing ? REVEAL_LABEL : HINT_LABEL}
            </p>
          ) : null}

          {/* The board, and the whole reason the child looks up.

              On it is the one thing this card is teaching, drawn rather than
              delivered: the letter is written while it is being said. The
              explanation is still not printed here — a paragraph of English on
              a blackboard is no more readable to a two-year-old than one
              anywhere else — and the everyday examples that used to be drawn
              under it are gone at the user's request, after a ball kept turning
              up beside a square and then beside a triangle. */}
          {!dayDone ? (
            <Blackboard
              title={turn?.topic_title}
              visualKind={turn?.visual_kind}
              visualValue={turn?.visual_value}
              playKey={boardKey}
            />
          ) : null}

          <div aria-live="polite" className="grid gap-3">
            {/* Said, not shown. A screen reader still gets the whole
                explanation; a child gets the picture above and the question
                below, which is all they can use. */}
            <p className="sr-only">{turn?.speech}</p>
            {busy && !turn ? (
              <p className="max-w-2xl text-xl font-bold leading-snug text-ink/80 sm:text-2xl">
                Waking the teacher up…
              </p>
            ) : null}
            {turn?.question ? (
              <p className="max-w-2xl text-3xl font-black leading-snug text-ink sm:text-4xl">
                {turn.question}
              </p>
            ) : null}
          </div>

          {/* The day is over. There is nothing to answer and nothing to open —
              the next lesson is tomorrow's, and the server is the thing that
              says so, so a reload lands right back here. */}
          {dayDone ? (
            <div className="grid justify-items-center gap-3" data-testid="day-complete">
              <p className="text-lg font-bold text-ink/60">
                Come back tomorrow for the next one.
              </p>
              <Link
                href="/adventure"
                className="pressable rounded-3xl bg-leaf px-8 py-4 text-xl font-black text-white shadow-soft"
              >
                🗺️ See my levels
              </Link>
            </div>
          ) : null}

          {/* Explaining is not a question: there is one thing to do, and it is
              to carry on. */}
          {turn?.expects === "ready" ? (
            <div className="grid justify-items-center gap-3">
              <button
                type="button"
                disabled={busy || speaking}
                onClick={() => void send("ready")}
                className="pressable rounded-3xl bg-leaf px-8 py-4 text-xl font-black text-white shadow-soft disabled:opacity-50"
              >
                {revealing ? "👍 I see - next one" : "👍 Got it - what next?"}
                {secondsLeft !== null ? ` (${secondsLeft})` : ""}
              </button>
              <p className="text-sm font-bold text-ink/50">
                {secondsLeft !== null
                  ? "Carrying on by itself - or ask me something first."
                  : " "}
              </p>
            </div>
          ) : null}

          {/* The drawing step. Nothing here is marked: the child draws it, and
              the lesson moves on when they have. */}
          {turn?.expects === "trace" && turn.trace_target ? (
            <div className="w-full max-w-md">
              <TraceCanvas
                target={turn.trace_target}
                minAccuracy={0.5}
                disabled={busy || speaking}
                onComplete={() => void send("done")}
              />
            </div>
          ) : null}

          {/* What to tap. The server says what was offered; it never says which
              one is right, so nothing here can give the answer away.

              Each one is drawn as a picture with its word underneath, because
              two words a child cannot read are the same button twice. The
              string sent back is the option exactly as it arrived - only how it
              is drawn changes here. */}
          {turn?.options?.length ? (
            <div className="flex flex-wrap items-center justify-center gap-3">
              {turn.options.map((option) => (
                <button
                  key={option}
                  type="button"
                  disabled={busy || speaking}
                  onClick={() => void send(option)}
                  className="pressable min-h-16 rounded-3xl bg-white px-6 py-4 shadow-soft disabled:opacity-50"
                >
                  <AnswerChoice option={option} offered={turn.options} />
                </button>
              ))}
            </div>
          ) : null}

          <div className={`flex flex-wrap items-center justify-center gap-3 ${dayDone ? "hidden" : ""}`}>
            <button
              type="button"
              onClick={() => void say([turn?.speech, turn?.question].filter(Boolean).join(" "))}
              disabled={!turn || speaking}
              className="pressable rounded-full bg-white px-5 py-3 text-base font-black text-ink shadow-soft disabled:opacity-50"
            >
              🔊 Say it again
            </button>
            {canListen ? (
              <button
                type="button"
                onClick={() => void askSomething()}
                // Not disabled while the guide is talking: interrupting it is
                // exactly what this button is for, and the handler stops the
                // speech itself. Waiting for a long explanation to finish is
                // indistinguishable from a button that does not work.
                disabled={!turn || busy || listening}
                className={`pressable rounded-full px-5 py-3 text-base font-black shadow-soft disabled:opacity-50 ${
                  listening ? "animate-pulse bg-leaf text-white" : "bg-white text-ink"
                }`}
              >
                🙋 Ask me anything
              </button>
            ) : null}
            {canListen && turn?.expects !== "ready" && turn?.expects !== "trace" ? (
              <button
                type="button"
                onClick={() => void speakAnswer()}
                // Likewise: a child who already knows the answer should not have
                // to sit through the rest of the sentence to say it. Edge TTS
                // plays the whole clip, so this window is seconds long — quite
                // long enough to look like a dead microphone.
                disabled={!turn || busy || listening}
                className={`pressable grid h-20 w-20 place-items-center rounded-full text-3xl shadow-soft disabled:opacity-60 ${
                  listening ? "animate-pulse bg-leaf text-white" : "bg-sunshine text-ink"
                }`}
                aria-label={listening ? "Listening" : "Answer out loud"}
              >
                🎤
              </button>
            ) : null}
          </div>

          {/* What the microphone is doing, in words, because a four-year-old
              cannot tell a pulsing circle from a decoration. */}
          {turn?.question && turn.expects !== "ready" && turn.expects !== "trace" && !dayDone ? (
            <p
              aria-live="polite"
              className={`text-lg font-black ${listening ? "text-leaf" : "text-ink/50"}`}
            >
              {listening
                ? micLevel >= HEARD_LEVEL
                  ? "🎤 I can hear you…"
                  : "🎤 I am listening… say it out loud!"
                : speaking
                  ? ""
                  : SPEAK_NOW}
            </p>
          ) : null}

          {/* The level, while the microphone is open.
              A child who can watch the bar move when they talk quietly stops
              shouting at the screen, and a grown-up can tell at a glance
              whether the microphone is dead or the answer simply was not a word
              the recogniser knew. */}
          {listening ? (
            <div
              className="h-3 w-full max-w-xs overflow-hidden rounded-full bg-ink/10"
              role="presentation"
            >
              <div
                className={`h-full rounded-full transition-[width] duration-75 ${
                  micLevel >= HEARD_LEVEL ? "bg-leaf" : "bg-ink/25"
                }`}
                style={{ width: `${Math.max(4, Math.round(micLevel * 100))}%` }}
              />
            </div>
          ) : null}

          {/* Why the microphone did not answer. For the grown-up sitting
              alongside — the child has the options and the typing box either
              way, so a broken mic never blocks the lesson. */}
          {micNote && !dayDone ? (
            <p
              data-testid="mic-note"
              aria-live="polite"
              className="max-w-md rounded-2xl bg-sunshine/30 px-5 py-3 text-base font-bold text-ink/80"
            >
              🎤 {micNote}
            </p>
          ) : null}

          {/* Typing is here for the grown-up sitting alongside, and for a
              browser with no microphone. */}
          {turn?.expects === "ready" || turn?.expects === "trace" || dayDone ? null : (
          <form onSubmit={onSubmit} className="flex w-full max-w-md flex-wrap justify-center gap-3">
            <input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              placeholder="Type the answer"
              aria-label="Type the answer"
              disabled={!turn || busy}
              className="min-h-14 min-w-0 flex-1 rounded-2xl border-2 border-leaf/20 bg-white px-5 py-3 text-lg font-bold text-ink outline-none focus:border-sky"
            />
            <button
              type="submit"
              disabled={!turn || busy || !typed.trim()}
              className="pressable rounded-2xl bg-sky px-6 py-3 text-lg font-black text-white shadow-soft disabled:opacity-50"
            >
              Answer
            </button>
          </form>
          )}
        </div>

        {/* What the bot actually did this turn, for the grown-up reading along:
            which of the nine strategies it taught with and where the words came
            from. The verdict is not in this list because the model has nothing
            to do with it — `stage.judge` marks the answer in plain Python. */}
        {turn && !dayDone ? (
          <p className="text-center text-sm font-bold text-ink/40">
            strategy {turn.strategy} · words from {turn.source === "llm" ? "the model" : "the notes"} ·
            retrieval {turn.retrieval} · answers are marked by the server, never by the model
          </p>
        ) : null}
      </section>
    </AppShell>
  );
}
