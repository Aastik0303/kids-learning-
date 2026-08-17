"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ActivityView } from "@/components/curriculum/ActivityView";
import { ComingSoon } from "@/components/curriculum/ComingSoon";
import { AppShell } from "@/components/shared/AppShell";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import type { VisualGuideAction } from "@/components/guide/VisualGuideRenderer";
import { FALLBACK_MODE, showsText } from "@/lib/experience";
import { getExperienceMode, getTopic } from "@/services/curriculum";
import {
  activityQuestion,
  askGuideQuestion,
  GUIDE_TARGETS,
  guideAgent,
  isSafeGuideTarget,
  progressContext,
  visualTargetsForActivity
} from "@/services/guide";
import { answerLearning, startLearning } from "@/services/learning";
import { getProgress } from "@/services/child";
import { getChild, saveChild } from "@/services/session";
import type { Activity, ExperienceMode, GuideEvent, LearningResponse, Topic } from "@/types";

/** A beat, so praise for the last answer is not cut off by the next question. */
const PRAISE_PAUSE_MS = 900;

const QUESTION_TARGETS = [
  GUIDE_TARGETS.QUESTION_AREA,
  GUIDE_TARGETS.COUNTING_OBJECTS,
  GUIDE_TARGETS.ANSWER_OPTIONS,
  GUIDE_TARGETS.ACTIVITY_AREA,
  GUIDE_TARGETS.VOICE_ANSWER_AREA
];

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function TopicLessonPage({
  params
}: {
  params: Promise<{ subjectId: string; topicId: string }>;
}) {
  const { subjectId, topicId } = use(params);
  const [topic, setTopic] = useState<Topic | null>(null);
  const [mode, setMode] = useState<ExperienceMode>(FALLBACK_MODE);
  const [session, setSession] = useState<LearningResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // --- the guide, inside the lesson ---------------------------------------
  // A lesson used to run in silence: the question appeared and nothing said
  // what it meant. Practice already had a guide doing exactly this, so the
  // same one now teaches here — it explains every question aloud, hints after
  // a miss, and points at what to look at. It never decides correctness: that
  // is the server's, and only the server's.
  const [guideMessage, setGuideMessage] = useState("");
  const [guideBusy, setGuideBusy] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [visualAction, setVisualAction] = useState<VisualGuideAction>(null);
  const [countGuideEnabled, setCountGuideEnabled] = useState(false);

  const { setAvatar, speakMessage } = useAvatar();
  // A late guide reply must never speak over a newer one.
  const guideRequestRef = useRef(0);
  const praisePauseRef = useRef(0);
  const activityRef = useRef<Activity | null>(null);
  const firstQuestionRef = useRef(true);

  const route = `/adventure/${subjectId}/${topicId}`;

  const clearPointing = useCallback(() => {
    setHighlightId(null);
    setVisualAction(null);
    setCountGuideEnabled(false);
  }, []);

  /**
   * One guide turn. Applies the reply only if it is still the newest one, and
   * speaks it after any praise still in the air has had its moment.
   */
  const runGuide = useCallback(
    async ({
      event,
      activity,
      sessionId,
      attempt = 0,
      childAnswer,
      pointing,
      highlightOnly = false
    }: {
      event: GuideEvent;
      activity: Activity | null;
      sessionId: string;
      attempt?: number;
      childAnswer?: string;
      /** Whether this turn may point at the pictures and number them. */
      pointing: boolean;
      /** Light up one button — what a finished lesson does, and nothing more. */
      highlightOnly?: boolean;
    }) => {
      const child = getChild();
      if (!child) return;
      const requestId = ++guideRequestRef.current;
      setGuideBusy(true);
      try {
        const guide = await guideAgent({
          session_id: sessionId,
          child_id: child.child_id,
          mode: "learning",
          event,
          route,
          screen: "topic_lesson",
          feature: `${topicId}_lesson`,
          class_id: child.class_id,
          experience_mode: child.experience_mode,
          preferred_language: child.preferred_language,
          question: activity
            ? activityQuestion(activity, {
                topic: topicId,
                concept: activity.type,
                attempt,
                child_answer: childAnswer,
                recent_answers: childAnswer ? [childAnswer] : []
              })
            : undefined,
          progress: progressContext(child, subjectId, topicId),
          available_actions: pointing ? ["show_hint", "highlight", "repeat_instruction"] : ["highlight"],
          available_targets: activity ? QUESTION_TARGETS : [GUIDE_TARGETS.OPEN_SUBJECTS],
          allowed_visual_targets: activity ? visualTargetsForActivity(activity) : []
        });
        if (requestId !== guideRequestRef.current) return;

        setGuideMessage(guide.message);
        setGuideBusy(false);
        // The avatar carries the words; the speaking is done here so the pause
        // after praise is honoured instead of two lines talking over each other.
        setAvatar({ ...guide.avatar, speak: false });
        if (pointing) {
          setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
          setVisualAction(guide.visual_action);
          setCountGuideEnabled(true);
        } else if (highlightOnly) {
          setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
          setVisualAction(null);
          setCountGuideEnabled(false);
        } else {
          clearPointing();
        }

        const pause = praisePauseRef.current;
        praisePauseRef.current = 0;
        if (pause) await wait(pause);
        if (requestId !== guideRequestRef.current) return;
        speakMessage(guide.message);
      } finally {
        if (requestId === guideRequestRef.current) setGuideBusy(false);
      }
    },
    [clearPointing, route, setAvatar, speakMessage, subjectId, topicId]
  );

  useEffect(() => {
    const child = getChild();
    getTopic(topicId)
      .then(async (next) => {
        if (!child || next.class_id !== child.class_id || next.subject_id !== subjectId) {
          throw new Error("This topic belongs to a different class.");
        }
        setTopic(next);
        setMode(await getExperienceMode(next.class_id));
        if (!next.available) return;
        const started = await startLearning(child.child_id, next.topic_id);
        setSession(started);
        if (started.avatar) setAvatar({ ...started.avatar, speak: false });
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "We could not open that topic."));
  }, [topicId, subjectId, setAvatar]);

  const activity = session?.activity ?? null;
  const activityId = activity?.activity_id ?? null;
  const sessionId = session?.session_id ?? "";
  activityRef.current = activity;

  // Every question is explained when it arrives — the first one, and each one
  // after it, including a question swapped in after too many misses.
  useEffect(() => {
    if (!activityId || !sessionId) return;
    const current = activityRef.current;
    if (!current) return;
    clearPointing();
    const event: GuideEvent = firstQuestionRef.current ? "TOPIC_STARTED" : "TOPIC_QUESTION_LOADED";
    firstQuestionRef.current = false;
    void runGuide({ event, activity: current, sessionId, pointing: false });
  }, [activityId, sessionId, clearPointing, runGuide]);

  /** The child asked something — by tapping Hint, or out loud into the mic. */
  const askGuide = useCallback(
    async (question: string) => {
      const current = activityRef.current;
      if (!sessionId) return;
      const requestId = ++guideRequestRef.current;
      setGuideBusy(true);
      setAvatar({ state: "thinking", message: "Let me help with that…", animationEffect: "pulse", durationMs: null });
      try {
        const guide = await askGuideQuestion({
          question,
          route,
          sessionId,
          screen: "topic_lesson",
          activity: current ?? undefined,
          topic: topicId,
          attempt: session?.attempt_number ?? 0
        });
        if (requestId !== guideRequestRef.current) return;
        setGuideMessage(guide.message);
        setGuideBusy(false);
        setAvatar({ ...guide.avatar, speak: false });
        setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
        setVisualAction(guide.visual_action);
        setCountGuideEnabled(true);
        speakMessage(guide.message);
      } finally {
        if (requestId === guideRequestRef.current) setGuideBusy(false);
      }
    },
    [route, session?.attempt_number, sessionId, setAvatar, speakMessage, topicId]
  );

  const submit = useCallback(
    async (answer: string) => {
      if (!session || busy) return;
      setBusy(true);
      // A hint still on its way must not land on top of the next question.
      guideRequestRef.current += 1;
      setGuideBusy(false);
      try {
        const next = await answerLearning(session.session_id, answer);
        setSession(next);

        if (next.complete) {
          // The unlock and the new stars happen on the server. The stored child
          // is a snapshot taken before this lesson, so without refreshing it the
          // topic list still draws the next level as locked and the star count
          // never moves.
          const refreshed = await getProgress(next.child_id);
          saveChild(refreshed.child);
          clearPointing();
          if (next.avatar) setAvatar({ ...next.avatar, speak: true });
          setGuideMessage(next.feedback || "");
          praisePauseRef.current = PRAISE_PAUSE_MS;
          void runGuide({
            event: "TOPIC_COMPLETED",
            activity: null,
            sessionId: next.session_id,
            pointing: false,
            highlightOnly: true
          });
          return;
        }

        if (next.is_correct === true) {
          clearPointing();
          if (next.avatar) setAvatar({ ...next.avatar, speak: true });
          setGuideMessage(next.feedback || "");
          // The next question explains itself once it arrives; leave it room.
          praisePauseRef.current = PRAISE_PAUSE_MS;
          return;
        }

        if (next.is_correct === false && next.activity && !next.question_changed) {
          // Wrong, same question: the guide coaches the retry. The server has
          // already decided it was wrong — the guide only says what to look at.
          void runGuide({
            event: "TOPIC_ANSWER_INCORRECT",
            activity: next.activity,
            sessionId: next.session_id,
            attempt: next.attempt_number,
            childAnswer: answer,
            pointing: next.attempt_number >= 2
          });
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Let us try that again.");
      } finally {
        setBusy(false);
      }
    },
    [session, busy, clearPointing, runGuide, setAvatar]
  );

  const withText = showsText(mode);
  const progressPercent = session?.activity_total
    ? Math.round((session.activity_index / session.activity_total) * 100)
    : 0;

  return (
    <AppShell>
      <div className="grid gap-4 sm:gap-6">
        <Link href={`/adventure/${subjectId}`} className="font-bold text-ink/60">
          ← Back
        </Link>

        {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}

        {topic && !topic.available ? <ComingSoon title={topic.title} mode={mode} /> : null}

        {session ? (
          <section id="activity-area" data-testid="activity-area" className="grid gap-4 sm:gap-6">
            <header className="grid gap-2">
              <h1 className="text-2xl font-black leading-tight sm:text-3xl md:text-4xl">{session.topic_title}</h1>
              {/* What this level is about, before the first question. A lesson
                  that opens straight into a question never says what it is for. */}
              {topic?.easy_line ? (
                <p className="text-base font-bold text-ink/70 sm:text-lg">{topic.easy_line}</p>
              ) : null}
              <div className="flex flex-wrap items-center gap-3">
                <p className="font-bold text-ink/60">
                  {session.activity_index} of {session.activity_total}
                </p>
                <div className="h-3 min-w-[8rem] flex-1 overflow-hidden rounded-full bg-sky/10">
                  <div
                    className="h-full rounded-full bg-leaf transition-[width] duration-300"
                    style={{ width: `${Math.min(progressPercent, 100)}%` }}
                  />
                </div>
              </div>
            </header>

            {/* The points this level covers, each in its own words. Folded away
                by default so it explains the level without crowding it. */}
            {withText && topic?.subtopics.length ? (
              <details className="surface-panel rounded-[2rem] p-4">
                <summary className="cursor-pointer text-lg font-black text-ink">
                  🔎 What we will learn
                </summary>
                <ul className="mt-3 grid gap-2">
                  {topic.subtopics.map((subtopic, position) => (
                    <li key={subtopic} className="flex items-start gap-2 font-bold text-ink/70">
                      <span aria-hidden>{topic.subtopic_icons?.[position] ?? "⭐"}</span>
                      <span>
                        {subtopic}
                        {topic.subtopic_easy?.[position] ? (
                          <span className="block font-bold text-ink/50">
                            {topic.subtopic_easy[position]}
                          </span>
                        ) : null}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}

            <p className="text-xl font-black sm:text-2xl">{session.tutor_response}</p>

            {session.activity ? (
              <ActivityView
                activity={session.activity}
                mode={mode}
                sessionId={session.session_id}
                onAnswer={submit}
                disabled={busy}
                isCorrect={session.is_correct}
                attemptNumber={session.attempt_number}
                hint={session.feedback}
                guideMessage={guideMessage}
                guideBusy={guideBusy}
                onHint={() => void askGuide("Can you give me a hint for this question?")}
                onShowMe={() => void askGuide("I don't understand. Show me and count each one with me.")}
                onGuideQuestion={askGuide}
                highlightId={highlightId}
                visualAction={visualAction}
                countGuideEnabled={countGuideEnabled}
              />
            ) : null}

            {session.feedback ? <p className="text-lg font-black sm:text-xl">{session.feedback}</p> : null}

            {/* The end of a lesson is where the levels belong. A child comes
                straight into their current lesson from the subject card, so the
                map of levels is the reward at the finish — with the one that
                just opened waiting on it — not a menu they had to get past
                first. */}
            {session.complete ? (
              <div className="grid gap-3">
                <p className="text-xl font-black sm:text-2xl">
                  {session.topic_completed ? "Topic complete! ⭐" : "Let us practise this one more."}
                </p>
                {session.topic_completed && session.next_topic_unlocked ? (
                  <p className="text-lg font-bold text-ink/70 sm:text-xl">🔓 A new level just opened!</p>
                ) : null}
                <Link
                  href={`/adventure/${subjectId}`}
                  data-testid="see-levels"
                  data-guide-id="open-subjects"
                  className={`pressable rounded-3xl bg-leaf px-6 py-4 text-center text-lg font-black text-white shadow-soft sm:text-xl ${
                    highlightId === "open-subjects" ? "guide-glow" : ""
                  }`}
                >
                  🗺️ See my levels
                </Link>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
