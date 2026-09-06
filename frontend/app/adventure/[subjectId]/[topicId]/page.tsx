"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { ComingSoon } from "@/components/curriculum/ComingSoon";
import { ExampleStrip } from "@/components/curriculum/ExampleStrip";
import { AppShell } from "@/components/shared/AppShell";
import { FALLBACK_MODE, showsText } from "@/lib/experience";
import { useActiveChild } from "@/lib/useActiveChild";
import { useTodayPlan } from "@/lib/useTodayPlan";
import { getExperienceMode, getTopic, getTopicNotes } from "@/services/curriculum";
import { canSpeak, speakText, stopSpeech } from "@/services/speech";
import type { ExperienceMode, Topic, TopicNotes } from "@/types";

/**
 * A level on the Adventure map, and what it is.
 *
 * This page used to teach. First it drove `/learning` itself, then it rendered
 * the conductor's sitting with the level named — either way, opening a level
 * here was a second way into a lesson, running beside the class and able to
 * finish a level the schedule had not reached.
 *
 * There is one class now and it is the AI Teacher: it runs one stage per item of
 * today's frozen plan, marks the level done when the stage is through, and
 * unlocks the next one. Adventure is where a child *sees* that happen. So this
 * page says what the level is, where it stands — finished, today's, sleeping
 * until its turn, or still locked — and offers no way to start it, because
 * starting a level was never this page's decision to make. The way in is the
 * class, and the schedule decides when.
 *
 * It does one more thing, and it is the reason a child would come here at all:
 * it gives back **the notes for this level** — what it teaches, in the words
 * the syllabus author wrote, with the everyday pictures beside them — and reads
 * them out loud, because a three-year-old cannot read a line of it. Going back
 * over something is how it stops fading, and there was nowhere in the app to do
 * that.
 *
 * The notes are deterministic all the way down (`app/playground/notes.py`): no
 * model writes them, so the same level says the same thing on every afternoon.
 * Opening them marks nothing, scores nothing, unlocks nothing and does not move
 * the day's plan — which is what keeps this a progress board rather than a
 * second classroom.
 */
export default function TopicLevelPage({
  params
}: {
  params: Promise<{ subjectId: string; topicId: string }>;
}) {
  const { subjectId, topicId } = use(params);
  const { child } = useActiveChild();
  const { plannedTopicIds, loaded } = useTodayPlan(child);
  const [topic, setTopic] = useState<Topic | null>(null);
  const [mode, setMode] = useState<ExperienceMode>(FALLBACK_MODE);
  const [notes, setNotes] = useState<TopicNotes | null>(null);
  const [reading, setReading] = useState(false);

  useEffect(() => {
    getTopic(topicId)
      .then(setTopic)
      .catch(() => setTopic(null));
  }, [topicId]);

  useEffect(() => {
    getTopicNotes(topicId)
      // Notes are the nice-to-have on this page: a level whose notes cannot be
      // fetched still shows what it is and where it stands.
      .then(setNotes)
      .catch(() => setNotes(null));
  }, [topicId]);

  // Leaving the page mid-sentence must not leave the voice talking over the
  // next screen — the class narrates too, and two of them at once is chaos.
  useEffect(() => () => stopSpeech(), []);

  const readAloud = useCallback(() => {
    if (!notes?.speech) return;
    if (reading) {
      stopSpeech();
      setReading(false);
      return;
    }
    setReading(true);
    // The same voice the class uses: Edge through this app's own backend, with
    // the device's own voice only as a fallback. `speakText` owns that choice;
    // nothing here picks a voice or a language.
    const started = speakText(notes.speech, () => setReading(false));
    if (!started) setReading(false);
  }, [notes, reading]);

  useEffect(() => {
    if (!child) return;
    getExperienceMode(child.class_id)
      .then(setMode)
      .catch(() => setMode(FALLBACK_MODE));
  }, [child]);

  /**
   * Where this level stands. The same four answers the map itself gives, read
   * from the same two places: the child's own board says what is finished and
   * what is open, and today's plan says which of the open ones is today's.
   */
  const standing = useMemo(() => {
    const progress = child?.subject_progress?.[subjectId];
    if (progress?.completed_topics.includes(topicId)) {
      return { icon: "⭐", label: "Finished", detail: "You have already done this one." };
    }
    if (!progress?.unlocked_topics.includes(topicId)) {
      return {
        icon: "🔒",
        label: "Locked",
        detail: "Finish the levels before this one and it will open."
      };
    }
    // Nothing is called tomorrow's on a guess: a slow read of the plan must not
    // make today's own level look shut.
    if (loaded && plannedTopicIds.size > 0 && !plannedTopicIds.has(topicId)) {
      return {
        icon: "🌙",
        label: "Waiting for its turn",
        detail: "It is not on today's list. Your class will bring you here."
      };
    }
    return {
      icon: "🎈",
      label: "On today's list",
      detail: "Your class is teaching this one today."
    };
  }, [child, subjectId, topicId, plannedTopicIds, loaded]);

  const backToLevels = (
    <Link href={`/adventure/${subjectId}`} className="font-bold text-ink/60">
      ← Back
    </Link>
  );

  // A level with nothing authored behind it is said so plainly.
  if (topic && !topic.available) {
    return (
      <AppShell>
        <div className="grid gap-4">
          {backToLevels}
          <ComingSoon title={topic.title} mode={mode} />
        </div>
      </AppShell>
    );
  }

  const withText = showsText(mode);

  return (
    <AppShell>
      <div className="grid gap-5">
        {backToLevels}

        <header className="surface-panel grid gap-3 rounded-[2rem] p-5">
          <div className="flex flex-wrap items-center gap-3">
            <span aria-hidden className="text-5xl">
              {topic?.icon ?? "🎈"}
            </span>
            <div className="grid gap-1">
              <h1 className="text-2xl font-black leading-tight sm:text-3xl md:text-4xl">
                {topic?.title ?? "Your level"}
              </h1>
              <p
                data-testid="level-standing"
                className="text-base font-black uppercase tracking-wide text-ink/45"
              >
                {standing.icon} {standing.label}
              </p>
            </div>
          </div>

          {topic?.easy_line ? (
            <p className="text-base font-bold text-ink/70 sm:text-lg">{topic.easy_line}</p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-white px-4 py-2 font-black text-ink/70 shadow-soft">
              {topic?.activity_count ?? 0} activities · ⭐ {topic?.star_reward ?? 0}
            </span>
          </div>
        </header>

        {/* Why there is no "start" button here, said plainly rather than left
            as an absence for a grown-up to puzzle over. */}
        <section className="lift-card grid gap-3 rounded-[2rem] p-5">
          <p className="text-lg font-bold text-ink/70">{standing.detail}</p>
          <Link
            href="/ai-teacher"
            data-testid="go-to-class"
            className="pressable justify-self-start rounded-3xl bg-leaf px-6 py-4 text-lg font-black text-white shadow-soft sm:text-xl"
          >
            🧑‍🏫 Go to my class
          </Link>
        </section>

        {/*
          The notes: what this level teaches, in the author's own words, said
          out loud.

          Shown for every level except a locked one. A locked level is one the
          child has not been given yet, and handing over its notes would be
          teaching it early through the back door — the same reason the map does
          not link to it.

          The 🔊 button is the point of the page for a pre-reader: the lines are
          printed for the grown-up sitting alongside and *spoken* for the child,
          which is the same split the class makes. It is a button and not an
          autoplay, because a page a child navigated to should not start talking
          at them.
        */}
        {standing.label !== "Locked" && notes ? (
          <section
            data-testid="topic-notes"
            className="surface-panel grid gap-4 rounded-[2rem] p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-black text-ink">📖 Let us remember this one</h2>
              {notes.has_notes && canSpeak() ? (
                <button
                  type="button"
                  onClick={readAloud}
                  data-testid="read-notes"
                  aria-label={reading ? "Stop reading" : "Read these notes to me"}
                  className="pressable rounded-3xl bg-sky px-6 py-4 text-lg font-black text-white shadow-soft"
                >
                  {reading ? "⏹️ Stop" : "🔊 Read it to me"}
                </button>
              ) : null}
            </div>

            {notes.has_notes ? (
              <>
                {/* The pictures first: they are what a child who cannot read
                    actually takes in, and the words below are for the ear and
                    for the grown-up. */}
                <ExampleStrip items={notes.example_items} />
                <ul className="grid gap-2">
                  {notes.lines.map((line) => (
                    <li key={line} className="flex items-start gap-2 text-lg font-bold text-ink/75">
                      <span aria-hidden>•</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              // An honest empty state. A level whose author has not written the
              // teaching lines yet has nothing to revise from, and inventing
              // some would be the one thing this page must never do.
              <p className="font-bold text-ink/60">
                Your class will teach this one out loud. There is nothing written down for it yet.
              </p>
            )}
          </section>
        ) : null}

        {/* What this level covers, each point in its own words. */}
        {withText && topic?.subtopics.length ? (
          <section className="surface-panel grid gap-3 rounded-[2rem] p-5">
            <h2 className="text-lg font-black text-ink">🔎 What this level teaches</h2>
            <ul className="grid gap-2">
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
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
