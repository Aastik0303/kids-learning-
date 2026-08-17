"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ActivityView } from "@/components/curriculum/ActivityView";
import { ComingSoon } from "@/components/curriculum/ComingSoon";
import { AppShell } from "@/components/shared/AppShell";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { FALLBACK_MODE, showsText } from "@/lib/experience";
import { getExperienceMode, getTopic } from "@/services/curriculum";
import { answerLearning, startLearning } from "@/services/learning";
import { getProgress } from "@/services/child";
import { getChild, saveChild } from "@/services/session";
import type { ExperienceMode, LearningResponse, Topic } from "@/types";

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
  const { setAvatar } = useAvatar();

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
        if (started.avatar) setAvatar(started.avatar);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "We could not open that topic."));
  }, [topicId, setAvatar]);

  const submit = useCallback(
    async (answer: string) => {
      if (!session || busy) return;
      setBusy(true);
      try {
        const next = await answerLearning(session.session_id, answer);
        setSession(next);
        if (next.avatar) setAvatar(next.avatar);
        if (next.complete) {
          // The unlock and the new stars happen on the server. The stored child
          // is a snapshot taken before this lesson, so without refreshing it the
          // topic list still draws the next level as locked and the star count
          // never moves.
          const refreshed = await getProgress(next.child_id);
          saveChild(refreshed.child);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Let us try that again.");
      } finally {
        setBusy(false);
      }
    },
    [session, busy, setAvatar]
  );

  const withText = showsText(mode);

  return (
    <AppShell>
      <div className="grid gap-6">
        <Link href={`/adventure/${subjectId}`} className="font-bold text-ink/60">
          ← Back
        </Link>

        {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}

        {topic && !topic.available ? <ComingSoon title={topic.title} mode={mode} /> : null}

        {session ? (
          <section id="activity-area" data-testid="activity-area" className="grid gap-6">
            <header className="grid gap-1">
              <h1 className="text-3xl font-black">{session.topic_title}</h1>
              {/* What this level is about, before the first question. A lesson
                  that opens straight into a question never says what it is for. */}
              {topic?.easy_line ? (
                <p className="text-lg font-bold text-ink/70">{topic.easy_line}</p>
              ) : null}
              <p className="font-bold text-ink/60">
                {session.activity_index} of {session.activity_total}
              </p>
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

            <p className="text-2xl font-black">{session.tutor_response}</p>

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
              />
            ) : null}

            {session.feedback ? <p className="text-xl font-black">{session.feedback}</p> : null}

            {/* The end of a lesson is where the levels belong. A child comes
                straight into their current lesson from the subject card, so the
                map of levels is the reward at the finish — with the one that
                just opened waiting on it — not a menu they had to get past
                first. */}
            {session.complete ? (
              <div className="grid gap-3">
                <p className="text-2xl font-black">
                  {session.topic_completed ? "Topic complete! ⭐" : "Let us practise this one more."}
                </p>
                {session.topic_completed && session.next_topic_unlocked ? (
                  <p className="text-xl font-bold text-ink/70">🔓 A new level just opened!</p>
                ) : null}
                <Link
                  href={`/adventure/${subjectId}`}
                  data-testid="see-levels"
                  className="rounded-3xl bg-leaf px-6 py-4 text-center text-xl font-black text-white shadow-soft"
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
