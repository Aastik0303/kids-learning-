"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/shared/AppShell";
import { getProgress, seedChild } from "@/services/child";
import { getOrCreateGuestChild, saveChild } from "@/services/session";
import type { ChildProfile } from "@/types";

export default function ParentProgressPage() {
  const [child, setChild] = useState<ChildProfile | null>(null);

  async function refresh() {
    const stored = getOrCreateGuestChild();
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
            ? Object.entries(child.path_progress).map(([path, progress]) => (
                <div key={path} className="rounded-[2rem] bg-white p-5 shadow-soft">
                  <h2 className="text-2xl font-black capitalize">{path.replace("_", " ")}</h2>
                  <p className="font-bold">Completed stages: {progress.completed_stages.join(", ") || "None yet"}</p>
                  <p className="font-bold">Unlocked stages: {progress.unlocked_stages.join(", ")}</p>
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
