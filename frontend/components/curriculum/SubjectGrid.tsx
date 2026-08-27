"use client";

import Link from "next/link";
import type { ChildProfile, SubjectProgress, ClassDetail, Subject } from "@/types";
import { learningTargetStyle } from "@/lib/experience";
import { useTodayPlan } from "@/lib/useTodayPlan";

type Props = {
  detail: ClassDetail;
  child: ChildProfile | null;
};

/**
 * The child's class, rendered as its subjects — a progress board, not a menu.
 *
 * Every card goes to that subject's level map and nothing here starts a lesson.
 * The class is the AI Teacher and the frozen daily plan decides what it teaches,
 * so a card that opened a level would be a second way in, able to reach a level
 * the schedule had not got to yet. The "🗓️ Today" badge is how a child sees
 * whose turn it is.
 *
 * Names are always shown. `text_density: "none"` means a pre-reader should not
 * be *asked to read* to answer a question — it does not mean stripping the
 * labels off a menu, which left a screen of blank cards that neither the child
 * nor the grown-up beside them could use. The icon leads; the word supports it.
 */

// Accent -> gradient. Keyed by the accent the manifest gives each subject, so a
// new subject arrives with a look and this file never learns its name.
const ACCENTS: Record<string, { card: string; chip: string; bar: string }> = {
  sky: { card: "from-sky/25 via-white to-sunshine/20", chip: "bg-sky text-white", bar: "bg-sky" },
  leaf: { card: "from-leaf/25 via-white to-sky/15", chip: "bg-leaf text-white", bar: "bg-leaf" },
  berry: { card: "from-berry/20 via-white to-sunshine/20", chip: "bg-berry text-white", bar: "bg-berry" },
  sun: { card: "from-sunshine/35 via-white to-leaf/15", chip: "bg-sunshine text-ink", bar: "bg-sunshine" },
  ink: { card: "from-ink/10 via-white to-sky/15", chip: "bg-ink text-white", bar: "bg-ink" }
};

/**
 * Ink or white on top of a pinned colour, whichever a child can actually read.
 * The palette above already makes this call by hand — `sun` carries `text-ink`
 * because white on yellow is unreadable — so a colour that bypasses the palette
 * has to make it too, rather than defaulting to white and hoping.
 */
function readableOn(hex: string): string {
  const channel = (from: number) => {
    const part = parseInt(hex.slice(from, from + 2), 16) / 255;
    return part <= 0.03928 ? part / 12.92 : ((part + 0.055) / 1.055) ** 2.4;
  };
  const luminance = 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
  return luminance > 0.45 ? "#2f3b2a" : "#ffffff";
}

/**
 * A subject's look, from the manifest and nowhere else. `accent` names one of
 * the palette's gradients; `colour` pins an exact one for a subject whose brand
 * colour matters more than fitting the palette. Both are optional, so a subject
 * that gives neither still renders.
 */
function paletteOf(subject: Subject) {
  const accent = ACCENTS[subject.accent] ?? ACCENTS.leaf;
  if (!subject.colour) return { ...accent, cardStyle: {}, chipStyle: {}, barStyle: {} };

  const colour = subject.colour;
  return {
    card: "",
    chip: "",
    bar: "",
    // The same three-stop wash the palette gradients use, mixed from one colour.
    cardStyle: { backgroundImage: `linear-gradient(135deg, ${colour}40, #ffffff 55%, ${colour}26)` },
    chipStyle: { backgroundColor: colour, color: readableOn(colour) },
    barStyle: { backgroundColor: colour }
  };
}

/**
 * Whether this subject still has a level the child has not finished.
 *
 * A subject card used to start a lesson: it worked out which level the child was
 * on and dropped them into it. That is gone. The class is the AI Teacher and the
 * frozen daily plan decides which levels are taught today, so a card that
 * started a lesson would be a second way in — one that could open a level the
 * schedule had not reached. Every card goes to the subject's own level map now,
 * and this only decides what the card *says*.
 */
function hasMoreToDo(subject: Subject, progress: SubjectProgress | undefined): boolean {
  const completed = new Set(progress?.completed_topics ?? []);
  return subject.topics.some((topic) => topic.available && !completed.has(topic.topic_id));
}

export function SubjectGrid({ detail, child }: Props) {
  const mode = detail.experience;
  const { plannedTopicIds } = useTodayPlan(child);
  const totalDone = Object.values(child?.subject_progress ?? {}).reduce(
    (sum, progress) => sum + progress.completed_topics.length,
    0
  );

  return (
    <section className="grid gap-6">
      <header className="world-entrance grid gap-3 p-5 sm:p-7">
        <div className="relative z-10 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-white/80 px-4 py-2 text-sm font-black text-leaf shadow-soft">
            {detail.code} · ages {detail.min_age}–{detail.max_age}
          </span>
          <span className="rounded-full bg-sunshine px-4 py-2 text-sm font-black text-ink shadow-soft">
            ⭐ {child?.stars ?? 0}
          </span>
        </div>
        <h1 className="relative z-10 text-5xl font-black leading-tight text-ink sm:text-6xl">
          {detail.title}
        </h1>
        <p className="relative z-10 max-w-2xl text-xl font-bold text-ink/70">
          {detail.subtitle ? `${detail.subtitle} · ` : ""}
          {detail.subject_count} subjects · {totalDone} of {detail.topic_count} topics done
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        {detail.subjects.map((subject) => {
          const accent = paletteOf(subject);
          const progress = child?.subject_progress?.[subject.subject_id];
          const done = progress?.completed_topics.length ?? 0;
          const percent = subject.topic_count
            ? Math.round((done / subject.topic_count) * 100)
            : 0;
          const finished = done > 0 && done === subject.topic_count;
          const more = hasMoreToDo(subject, progress);
          const isToday = subject.topics.some((topic) => plannedTopicIds.has(topic.topic_id));
          // One destination: this subject's levels. Nothing on this screen
          // starts a lesson any more.
          const href = `/adventure/${subject.subject_id}` as const;

          const body = (
            <div className="grid h-full content-between gap-4">
              <div className="flex items-start gap-4">
                <span
                  aria-hidden
                  className="grid h-20 w-20 shrink-0 place-items-center rounded-[1.75rem] bg-white/85 text-4xl shadow-soft"
                >
                  {subject.icon}
                </span>
                <div className="grid gap-1">
                  {/* The child reads the fun name; the syllabus title stays
                      underneath it for the grown-up sitting alongside. */}
                  <h2 className="flex flex-wrap items-center gap-2 text-3xl font-black leading-tight text-ink">
                    {subject.fun_name ?? subject.title}
                    {isToday ? (
                      // Which subjects the day actually holds. A day is a few
                      // lessons and a class has more subjects than that, so the
                      // subjects take turns - this is how a child sees whose
                      // turn it is.
                      <span className="rounded-full bg-leaf/15 px-3 py-1 text-xs font-black uppercase tracking-wide text-leaf">
                        🗓️ Today
                      </span>
                    ) : null}
                  </h2>
                  {subject.fun_name ? (
                    <p className="text-sm font-black uppercase tracking-wide text-ink/40">
                      {subject.title}
                    </p>
                  ) : null}
                  {/* The friendly line wins when a subject has one: it says what
                      the subject *is*. `note` explains a grouping decision to a
                      grown-up reading the manifest, so it only fills the gap. */}
                  {subject.easy_line ? (
                    <p className="font-bold text-ink/70">{subject.easy_line}</p>
                  ) : subject.note ? (
                    <p className="font-bold text-ink/60">{subject.note}</p>
                  ) : (
                    <p className="font-bold text-ink/60">
                      {subject.topic_count} topics · {subject.activity_count} activities
                    </p>
                  )}
                </div>
              </div>

              {/* Each topic as a dot, so a child sees the shape of the journey. */}
              <div className="flex flex-wrap gap-1.5" aria-hidden>
                {subject.topics.map((topic) => {
                  const isDone = progress?.completed_topics.includes(topic.topic_id);
                  const isOpen = progress?.unlocked_topics.includes(topic.topic_id);
                  return (
                    <span
                      key={topic.topic_id}
                      title={topic.title}
                      style={isDone ? accent.chipStyle : undefined}
                      className={`grid h-8 w-8 place-items-center rounded-xl text-base ${
                        isDone ? accent.chip : isOpen ? "bg-white text-ink" : "bg-white/50 opacity-50"
                      }`}
                    >
                      {isDone ? "⭐" : topic.icon}
                    </span>
                  );
                })}
              </div>

              <div className="grid gap-2">
                <div className="progress-track">
                  <div
                    className={`h-full rounded-full ${accent.bar}`}
                    style={{ width: `${percent}%`, ...accent.barStyle }}
                  />
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="font-black text-ink/70">
                    {subject.available
                      ? finished
                        ? "🎉 All done!"
                        : `${done} of ${subject.topic_count} topics done`
                      : "🌱 Coming soon"}
                  </span>
                  {subject.available ? (
                    <span
                      style={accent.chipStyle}
                      className={`pressable rounded-2xl px-4 py-2 font-black shadow-soft ${accent.chip}`}
                    >
                      {isToday ? "In class today →" : more ? "My levels →" : "All finished →"}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          );

          const shared = `adventure-card bg-gradient-to-br ${accent.card} p-5`;
          const cardStyle = { ...learningTargetStyle(mode), ...accent.cardStyle };

          // One destination, so the whole card is one stretched link again.
          return subject.available ? (
            <div
              key={subject.subject_id}
              data-testid="subject-card"
              data-subject-id={subject.subject_id}
              data-available="true"
              style={cardStyle}
              className={shared}
            >
              {body}
              <Link
                id="subject-card"
                href={href}
                data-testid="subject-levels"
                aria-label={`${subject.fun_name ?? subject.title}: see my levels`}
                className="absolute inset-0 z-0 rounded-[2rem]"
              />
            </div>
          ) : (
            <div
              key={subject.subject_id}
              data-testid="subject-card"
              data-subject-id={subject.subject_id}
              data-available="false"
              style={cardStyle}
              className={`${shared} opacity-70`}
            >
              {body}
            </div>
          );
        })}
      </div>
    </section>
  );
}
