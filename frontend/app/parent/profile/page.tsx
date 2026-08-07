"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shared/AppShell";
import { pathAccents, pathSummaries } from "@/data/prototype";
import { getOrCreateGuestChild, getToken, getUser, isGuestSession, saveChild } from "@/services/session";
import { updateChildProfile } from "@/services/child";
import type { ChildProfile } from "@/types";

function progress(child: ChildProfile, pathId: string) {
  const total = pathSummaries.find((path) => path.path_id === pathId)?.total_stages ?? 8;
  return Math.round(((child.path_progress[pathId]?.completed_stages.length ?? 0) / total) * 100);
}

export default function ParentProfilePage() {
  const router = useRouter();
  const [child, setChild] = useState<ChildProfile | null>(null);
  const [selectedAge, setSelectedAge] = useState(4);
  const [profileMessage, setProfileMessage] = useState("");
  const [guest, setGuest] = useState(true);
  const [user, setUser] = useState<ReturnType<typeof getUser>>(null);

  useEffect(() => {
    const stored = getOrCreateGuestChild();
    setChild(stored);
    setSelectedAge(stored.age ?? 4);
    setGuest(isGuestSession());
    setUser(getUser());
  }, []);

  async function changeAge() {
    if (!child) return;
    const ageGroup = selectedAge < 2 ? "Under 2" : selectedAge === 2 ? "2 years" : selectedAge === 3 ? "3 years" : "4+ years";
    const updated = await updateChildProfile(getToken(), child, { age: selectedAge, age_group: ageGroup });
    saveChild(updated);
    setChild(updated);
    setProfileMessage(updated.learning_mode === "toddler" ? "Toddler mode is ready for this age." : "Standard learning mode is ready for this age.");
    router.push(updated.learning_mode === "toddler" ? "/toddler" : "/");
  }

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
              <div className="lift-card grid gap-3 rounded-[2rem] p-6">
                <p className="font-black text-ink/70">Learning Mode</p>
                <p className="text-2xl font-black text-ink">{child.learning_mode === "toddler" ? "Toddler" : "Standard"}</p>
                <label className="grid gap-2 font-black text-ink">
                  Change age
                  <select className="rounded-2xl border-2 border-leaf/20 bg-white px-4 py-4 font-black" value={selectedAge} onChange={(event) => setSelectedAge(Number(event.target.value))}>
                    <option value={1}>Under 2</option>
                    <option value={2}>2 years</option>
                    <option value={3}>3 years</option>
                    <option value={4}>4+ years</option>
                  </select>
                </label>
                <button type="button" className="pressable rounded-3xl bg-leaf px-5 py-4 text-xl font-black text-white shadow-soft" onClick={changeAge}>
                  Apply Age
                </button>
                {profileMessage ? <p className="rounded-2xl bg-leaf/10 p-3 font-black text-leaf">{profileMessage}</p> : null}
              </div>
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
