"use client";

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { ComingSoon } from "@/components/curriculum/ComingSoon";
import { LevelGames } from "@/components/games/LevelGames";
import { AppShell } from "@/components/shared/AppShell";
import { FALLBACK_MODE, showsText } from "@/lib/experience";
import { useActiveChild } from "@/lib/useActiveChild";
import { useTodayPlan } from "@/lib/useTodayPlan";
import { getExperienceMode, getTopic } from "@/services/curriculum";
import { stopSpeech } from "@/services/speech";
import type { ExperienceMode, Topic } from "@/types";

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
 * it hands the level back as **a game about the thing it teaches** — one of
 * find it, match the pairs or pop it, dealt at random and started straight
 * away. Going back over something is how it stops fading, and there was nowhere
 * in the app to do that. The child is not asked which game they want: three
 * cards to choose between is a menu, and a menu is a reading task.
 *
 * This used to be the level's *notes*: the author's teaching lines, printed and
 * read aloud. Revising by re-reading is a grown-up's skill, and the child this
 * page is for is three. They go back over something by playing with it again,
 * so the same authored content is dealt out as games instead
 * (`app/playground/games.py`).
 *
 * The games are deterministic all the way down: no model writes them, so the
 * same level offers the same three on every afternoon. Playing marks nothing,
 * scores nothing, unlocks nothing and does not move the day's plan — which is
 * what keeps this a progress board rather than a second classroom.
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

  useEffect(() => {
    getTopic(topicId)
      .then(setTopic)
      .catch(() => setTopic(null));
  }, [topicId]);

  // Leaving the page mid-sentence must not leave the voice talking over the
  // next screen — the games speak, the class speaks, and two of them at once is
  // chaos. The games stop their own voice as well; this is the backstop for
  // walking off the page while one is mid-sentence.
  useEffect(() => () => stopSpeech(), []);

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

  /** The level's own teaching points, drawn once and placed twice below. */
  const teaches = (
    <ul className="grid gap-2">
      {(topic?.subtopics ?? []).map((subtopic, position) => (
        <li key={subtopic} className="flex items-start gap-2 font-bold text-ink/70">
          <span aria-hidden>{topic?.subtopic_icons?.[position] ?? "⭐"}</span>
          <span>
            {subtopic}
            {topic?.subtopic_easy?.[position] ? (
              <span className="block font-bold text-ink/50">{topic.subtopic_easy[position]}</span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );

  return (
    // `fit` keeps the level on one screen on a phone and a tablet: what this
    // level is, where it stands, and the game - with nothing below the fold,
    // because a child who has come here to play should not have to scroll past
    // a paragraph to find it. See "One screen" in
    // globals.css; from xl: up the page flows as it always did.
    <AppShell fit>
      <div className="level-page grid gap-5">
        {backToLevels}

        <header className="level-head surface-panel grid gap-3 rounded-[2rem] p-5">
          <div className="flex flex-wrap items-center gap-3">
            <span aria-hidden className="level-icon text-5xl">
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
        <section className="level-standing lift-card grid gap-3 rounded-[2rem] p-5">
          <p className="text-base font-bold text-ink/70 sm:text-lg">{standing.detail}</p>
          <Link
            href="/ai-teacher"
            data-testid="go-to-class"
            className="pressable justify-self-start rounded-3xl bg-leaf px-6 py-4 text-lg font-black text-white shadow-soft sm:text-xl"
          >
            🧑‍🏫 Go to my class
          </Link>
        </section>

        {/*
          Three games about this level, where its notes used to be.

          Shown for every level except a locked one. A locked level is one the
          child has not been given yet, and handing over its games would be
          teaching it early through the back door — the same reason the map does
          not link to it, and the same rule the notes kept.

          Nothing in here is marked. No attempt, no probe, no episode, no star,
          no unlock and no movement of the day's plan: once the games have been
          fetched, everything a child taps stays in the browser. A game that
          paid stars would be a second classroom, and the class is the AI
          Teacher.
        */}
        {standing.label !== "Locked" ? <LevelGames topicId={topicId} /> : null}

        {/* What this level covers, each point in its own words.

            The same list twice, and it is worth saying why rather than reaching
            for a hook: it is a summary a grown-up opens on a phone or a tablet and a
            plain section on a laptop, and `<details open>` is an HTML attribute that
            cannot be set per breakpoint in CSS. Deciding it in JavaScript means
            reading the viewport during render, which is the one thing that
            makes the server and the browser disagree. So the markup says both
            and the breakpoint picks one.

            It is folded on the small screens because it is the only thing on
            this page written to be read: left open it was several inches of
            prose between a child and the games they came for. It is still here
            either way — one tap, not dropped. */}
        {withText && topic?.subtopics.length ? (
          <>
            <details className="surface-panel rounded-[2rem] p-5 xl:hidden">
              <summary className="cursor-pointer text-lg font-black text-ink">
                🔎 What this level teaches
              </summary>
              <div className="mt-3">{teaches}</div>
            </details>
            <section className="surface-panel hidden gap-3 rounded-[2rem] p-5 xl:grid">
              <h2 className="text-lg font-black text-ink">🔎 What this level teaches</h2>
              {teaches}
            </section>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
