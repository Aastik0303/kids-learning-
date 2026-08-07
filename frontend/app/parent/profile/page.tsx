"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shared/AppShell";
import { pathAccents, pathSummaries } from "@/data/prototype";
import { getOrCreateGuestChild, getUser, isGuestSession } from "@/services/session";
import type { ChildProfile } from "@/types";

function progress(child: ChildProfile, pathId: string) {
  const total = pathSummaries.find((path) => path.path_id === pathId)?.total_stages ?? 8;
  return Math.round(((child.path_progress[pathId]?.completed_stages.length ?? 0) / total) * 100);
}

export default function ParentProfilePage() {
  const [child, setChild] = useState<ChildProfile | null>(null);
  const [guest, setGuest] = useState(true);
  const [user, setUser] = useState<ReturnType<typeof getUser>>(null);

  useEffect(() => {
    setChild(getOrCreateGuestChild());
    setGuest(isGuestSession());
    setUser(getUser());
  }, []);

  return (
    <AppShell>
      {guest ? (
        <section className="surface-panel mx-auto grid max-w-2xl gap-4 rounded-[2rem] p-6 text-center">
          <h1 className="text-4xl font-black text-ink">Parent dashboard is locked</h1>
          <p className="text-xl font-bold text-ink/70">Guest children can practice and try the first learning stages, but saved progress needs a parent account.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Link className="pressable rounded-3xl bg-leaf px-5 py-4 text-xl font-black text-white shadow-soft" href="/signup">
              Sign Up
            </Link>
            <Link className="pressable rounded-3xl bg-white px-5 py-4 text-xl font-black text-ink shadow-soft" href="/login">
              Parent Login
            </Link>
          </div>
        </section>
      ) : child ? (
        <section className="grid gap-5">
          <div className="surface-panel rounded-[2rem] p-6">
            <p className="text-sm font-black uppercase text-leaf">Parent Profile</p>
            <h1 className="mt-1 text-4xl font-black text-ink">{user?.name ?? "Parent"}</h1>
            <p className="mt-2 text-xl font-bold text-ink/70">Child: {child.name} | Age Group: {child.age_group} | Language: {child.preferred_language}</p>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
            <div className="surface-panel grid gap-4 rounded-[2rem] p-6">
              <h2 className="text-3xl font-black text-ink">Learning Progress</h2>
              {["numbers", "alphabets", "colours", "shapes", "mixed_final"].map((pathId) => {
                const value = progress(child, pathId);
                return (
                  <div key={pathId} className="grid gap-2">
                    <div className="flex justify-between gap-3 font-black text-ink">
                      <span>{pathAccents[pathId].label}</span>
                      <span>{value}%</span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${value}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>

            <aside className="grid gap-4">
              <div className="rounded-[2rem] bg-sunshine p-6 shadow-soft">
                <p className="font-black text-ink/70">Stars</p>
                <p className="text-5xl font-black text-ink">{child.stars}</p>
              </div>
              <div className="lift-card rounded-[2rem] p-6">
                <p className="font-black text-ink/70">Certificate</p>
                <p className="mt-1 text-2xl font-black text-ink">{child.certificate_unlocked ? "Unlocked" : "Waiting"}</p>
              </div>
            </aside>
          </div>
        </section>
      ) : null}
    </AppShell>
  );
}
