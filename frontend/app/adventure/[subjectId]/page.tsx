"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ComingSoon } from "@/components/curriculum/ComingSoon";
import { TopicList } from "@/components/curriculum/TopicList";
import { AppShell } from "@/components/shared/AppShell";
import { FALLBACK_MODE } from "@/lib/experience";
import { useActiveChild } from "@/lib/useActiveChild";
import { getExperienceMode, getSubject } from "@/services/curriculum";
import type { ExperienceMode, Subject } from "@/types";

export default function SubjectPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = use(params);
  // Which topics are open comes from the child's progress, so it has to be the
  // server's copy: a profile cached before this subject existed carries no
  // progress for it and draws every topic locked, first one included.
  const { child, status } = useActiveChild();
  const [subject, setSubject] = useState<Subject | null>(null);
  const [mode, setMode] = useState<ExperienceMode>(FALLBACK_MODE);
  const [error, setError] = useState("");

  useEffect(() => {
    if (status === "loading") return;
    getSubject(subjectId)
      .then(async (next) => {
        if (!child || next.class_id !== child.class_id) {
          setSubject(null);
          setError("This subject belongs to a different class.");
          return;
        }
        setSubject(next);
        setError("");
        setMode(await getExperienceMode(next.class_id));
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "We could not load that subject."));
  }, [subjectId, child, status]);

  return (
    <AppShell>
      <div className="grid gap-6">
        <Link href="/adventure" className="font-bold text-ink/60">
          ← All subjects
        </Link>
        {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}
        {subject ? (
          <>
            <header className="grid gap-1">
              <h1 className="text-3xl font-black">{subject.fun_name ?? subject.title}</h1>
              {subject.fun_name ? (
                <p className="text-sm font-black uppercase tracking-wide text-ink/40">{subject.title}</p>
              ) : null}
              {subject.easy_line ? (
                <p className="text-lg font-bold text-ink/70">{subject.easy_line}</p>
              ) : null}
              {subject.note ? <p className="font-bold text-ink/60">{subject.note}</p> : null}
            </header>
            {subject.available ? (
              <TopicList subject={subject} child={child} mode={mode} />
            ) : (
              <ComingSoon title={subject.title} mode={mode} />
            )}
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
