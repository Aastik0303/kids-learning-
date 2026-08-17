"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/shared/AppShell";
import { getProgress, seedChild } from "@/services/child";
import { getChild, saveChild } from "@/services/session";
import type { ChildProfile } from "@/types";

export default function ParentProgressPage() {
  const [child, setChild] = useState<ChildProfile | null>(null);

  async function refresh() {
    const stored = getChild();
    if (!stored) return;
    const response = await getProgress(stored.child_id);
    saveChild(response.child);
    setChild(response.child);
  }

  async function seed() {
    if (!child) return;
    const seeded = await seedChild(child.child_id);
    saveChild(seeded);
    setChild(seeded);
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="rounded-[2rem] bg-white p-6 shadow-soft">
          <h1 className="text-3xl font-black">{child?.name ?? "Child"} Progress</h1>
          <p className="mt-2 text-xl font-bold">Stars: {child?.stars ?? 0}</p>
        </div>
        <div className="grid gap-4">
          {child
            ? Object.entries(child.subject_progress).map(([subjectId, progress]) => (
                <div key={subjectId} className="rounded-[2rem] bg-white p-5 shadow-soft">
                  <h2 className="text-2xl font-black">{subjectId}</h2>
                  <p className="font-bold">Completed topics: {progress.completed_topics.join(", ") || "None yet"}</p>
                  <p className="font-bold">Unlocked topics: {progress.unlocked_topics.join(", ")}</p>
                </div>
              ))
            : null}
        </div>
        <button className="rounded-3xl bg-ink px-6 py-4 text-xl font-black text-white" onClick={seed}>
          Seed final demo
        </button>
      </section>
    </AppShell>
  );
}
