"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/shared/AppShell";
import { NoChildNotice } from "@/components/shared/NoChildNotice";
import { useActiveChild } from "@/lib/useActiveChild";
import { practiceSubjects, type PracticeSubject } from "@/services/practice";

/**
 * Practice is offered per subject, and only for the child's own class. Titles
 * come from the server, so this page contains no curriculum names.
 */
export default function PracticePage() {
  const { child, status, error } = useActiveChild();
  const [subjects, setSubjects] = useState<PracticeSubject[]>([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!child) return;
    practiceSubjects(child.child_id)
      .then(setSubjects)
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : "We could not load practice.")
      );
  }, [child]);

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="surface-panel flex flex-wrap items-end justify-between gap-3 rounded-[2rem] p-5">
          <div>
            <p className="text-sm font-black uppercase text-sky">Practice</p>
            <h1 className="text-4xl font-black text-ink sm:text-5xl">Choose a subject</h1>
          </div>
          <Link className="pressable rounded-full bg-white px-4 py-3 font-black text-ink shadow-soft" href="/">
            Back Home
          </Link>
        </div>

        {status === "loading" ? <p className="font-bold text-ink/60">Loading…</p> : null}
        {status !== "loading" && status !== "ready" ? <NoChildNotice status={status} error={error} /> : null}
        {loadError ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{loadError}</p> : null}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {subjects.map((subject, index) => {
            const openable = subject.unlocked;
            const card = (
              <div className="grid h-full content-between gap-5">
                <div className="grid gap-3">
                  <span className="grid h-20 w-20 place-items-center rounded-[1.75rem] bg-[#f5f8ef] text-2xl font-black shadow-soft">
                    {subject.icon}
                  </span>
                  <div>
                    {/* The child reads the fun name; the syllabus title stays
                        underneath it for the grown-up sitting alongside. */}
                    <h2 className="mt-3 text-3xl font-black text-ink">
                      {subject.fun_name ?? subject.title}
                    </h2>
                    {subject.fun_name ? (
                      <p className="text-sm font-black uppercase tracking-wide text-ink/40">
                        {subject.title}
                      </p>
                    ) : null}
                    {subject.easy_line ? (
                      <p className="mt-2 font-bold text-ink/70">{subject.easy_line}</p>
                    ) : null}
                    <p className="mt-2 text-lg font-bold text-ink/70">
                      {subject.has_activities
                        ? `${subject.topic_count} topics ready to practise`
                        : "Coming soon"}
                    </p>
                    {/* Which topics, not just how many — a child picking a card
                        should be able to see what they are about to be asked. */}
                    {subject.topic_titles?.length ? (
                      <ul className="mt-2 flex flex-wrap gap-1.5">
                        {subject.topic_titles.map((title) => (
                          <li
                            key={title}
                            className="rounded-full bg-[#f5f8ef] px-3 py-1 text-sm font-bold text-ink/70"
                          >
                            {title}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </div>
                <span className="pressable rounded-3xl bg-sunshine px-5 py-4 text-center text-xl font-black text-ink shadow-soft">
                  {openable ? "Start Practice" : "Not yet"}
                </span>
              </div>
            );

            return openable ? (
              <Link
                key={subject.subject_id}
                href={`/practice/${subject.subject_id}`}
                data-guide-id={index === 0 ? "start-practice" : undefined}
                data-testid="practice-subject"
                className="lift-card grid min-h-72 content-between gap-5 rounded-[2rem] p-6"
              >
                {card}
              </Link>
            ) : (
              <div
                key={subject.subject_id}
                data-testid="practice-subject"
                className="lift-card grid min-h-72 content-between gap-5 rounded-[2rem] p-6 opacity-70"
              >
                {card}
              </div>
            );
          })}
        </div>
      </section>
    </AppShell>
  );
}
