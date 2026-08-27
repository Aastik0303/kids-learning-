"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/shared/AppShell";
import { NoChildNotice } from "@/components/shared/NoChildNotice";
import { useActiveChild } from "@/lib/useActiveChild";
import { getProgress } from "@/services/child";
import { getClassForChild } from "@/services/curriculum";
import { getHistory, getPlanHistory, type ActivityAttempt, type PlanHistoryEntry } from "@/services/history";
import { saveChild } from "@/services/session";
import type { ChildProfile, ClassDetail } from "@/types";

/**
 * What actually happened, for the grown-up.
 *
 * This screen used to show a star count, raw subject ids and a "Seed final
 * demo" button. The three things a parent wants were all already on the server
 * and none of them were read: the attempt log (`/history`), the plans the
 * planner has frozen (`/plans/{id}/history`) and the subject titles from the
 * curriculum. It reads all three now, and titles come from the manifest so no
 * curriculum name is written into this file.
 */
export default function ParentProgressPage() {
  const { child: activeChild, status, error } = useActiveChild();
  const [child, setChild] = useState<ChildProfile | null>(null);
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [attempts, setAttempts] = useState<ActivityAttempt[]>([]);
  const [plans, setPlans] = useState<PlanHistoryEntry[]>([]);

  useEffect(() => {
    if (!activeChild) return;
    const childId = activeChild.child_id;
    getProgress(childId)
      .then((progress) => {
        saveChild(progress.child);
        setChild(progress.child);
      })
      .catch(() => setChild(activeChild));
    getClassForChild(childId).then(setDetail).catch(() => setDetail(null));
    getHistory(childId)
      .then((log) => setAttempts((log.attempts ?? []).slice(-25).reverse()))
      .catch(() => setAttempts([]));
    getPlanHistory(childId)
      .then((history) => setPlans(history.plans ?? []))
      .catch(() => setPlans([]));
  }, [activeChild]);

  const subjectTitle = (subjectId: string) =>
    detail?.subjects.find((subject) => subject.subject_id === subjectId)?.title ?? subjectId;
  const topicTitle = (topicId: string) => {
    for (const subject of detail?.subjects ?? []) {
      const topic = subject.topics.find((candidate) => candidate.topic_id === topicId);
      if (topic) return topic.title;
    }
    return topicId;
  };

  const answered = attempts.length;
  const right = attempts.filter((attempt) => attempt.is_correct).length;

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="surface-panel rounded-[2rem] p-6">
          <h1 className="text-3xl font-black text-ink">{child?.name ?? "Child"}&apos;s progress</h1>
          <div className="mt-3 flex flex-wrap gap-5 text-lg font-bold text-ink/70">
            <span>⭐ {child?.stars ?? 0} stars</span>
            <span>📝 {answered} recent answers</span>
            {answered ? <span>✅ {Math.round((right / answered) * 100)}% right first time</span> : null}
          </div>
        </div>

        {status !== "loading" && status !== "ready" ? <NoChildNotice status={status} error={error} /> : null}

        {/* Where they are in each subject, in the manifest's own words. */}
        <div className="grid gap-4 lg:grid-cols-2">
          {Object.entries(child?.subject_progress ?? {}).map(([subjectId, progress]) => (
            <div key={subjectId} className="surface-panel rounded-[2rem] p-5">
              <h2 className="text-xl font-black text-ink">{subjectTitle(subjectId)}</h2>
              <p className="mt-2 font-bold text-ink/70">
                Finished {progress.completed_topics.length} of {progress.unlocked_topics.length} opened so far
              </p>
              {progress.current_topic_id ? (
                <p className="mt-1 font-bold text-ink/60">Now on: {topicTitle(progress.current_topic_id)}</p>
              ) : null}
            </div>
          ))}
        </div>

        {/* The attempt log. Every answer the child gave, as the server recorded it. */}
        <div className="surface-panel rounded-[2rem] p-5">
          <h2 className="text-xl font-black text-ink">Recent answers</h2>
          {attempts.length ? (
            <ul className="mt-3 grid gap-2">
              {attempts.map((attempt) => (
                <li
                  key={attempt.id}
                  className="flex flex-wrap items-baseline justify-between gap-2 rounded-2xl bg-white/70 px-4 py-3"
                >
                  <span className="font-black text-ink">
                    {attempt.is_correct ? "✅" : "🔁"} {topicTitle(attempt.topic)}
                  </span>
                  <span className="font-bold text-ink/60">
                    said &ldquo;{attempt.child_answer || "—"}&rdquo;
                    {attempt.attempt_number > 1 ? ` · try ${attempt.attempt_number}` : ""}
                  </span>
                  <span className="text-sm font-bold text-ink/40">
                    {new Date(attempt.created_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 font-bold text-ink/60">Nothing answered yet.</p>
          )}
        </div>

        {/* The days the planner froze, and who froze them. */}
        <div className="surface-panel rounded-[2rem] p-5">
          <h2 className="text-xl font-black text-ink">The last few days</h2>
          {plans.length ? (
            <ul className="mt-3 grid gap-2">
              {plans.map((day) => (
                <li key={day.plan_date} className="rounded-2xl bg-white/70 px-4 py-3">
                  <p className="font-black text-ink">
                    {day.plan_date}
                    <span className="ml-2 text-sm font-bold text-ink/40">
                      {day.source === "planner_agent" ? "planned by the agent" : "planned by the schedule"}
                    </span>
                  </p>
                  <p className="font-bold text-ink/60">
                    {day.items.map((item) => `${item.done ? "✅" : "•"} ${item.title}`).join("   ") || "Nothing planned"}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 font-bold text-ink/60">No plans frozen yet.</p>
          )}
        </div>
      </section>
    </AppShell>
  );
}
