"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { HomeExperience } from "@/components/home/HomeExperience";
import { getChild, getOrCreateGuestChild, setChildAge } from "@/services/session";
import type { LearningMode } from "@/types";

const ageOptions = [
  { label: "👶 Under 2", age: 1, ageGroup: "Under 2" },
  { label: "🧒 2 years", age: 2, ageGroup: "2 years" },
  { label: "🌟 3 years", age: 3, ageGroup: "3 years" },
  { label: "🚀 4+ years", age: 4, ageGroup: "4+ years" }
];

export function AgeGate() {
  const router = useRouter();
  const [mode, setMode] = useState<LearningMode | null>(null);
  const [busyAge, setBusyAge] = useState<number | null>(null);

  useEffect(() => {
    const child = getChild();
    if (!child || child.age === null || child.age === undefined) {
      getOrCreateGuestChild();
      setMode(null);
      return;
    }
    const nextMode = child.age < 3 ? "toddler" : "standard";
    if (nextMode === "toddler") router.replace("/toddler");
    setMode(nextMode);
  }, [router]);

  function chooseAge(age: number, ageGroup: string) {
    setBusyAge(age);
    setChildAge(age, ageGroup);

    const nextMode = age < 3 ? "toddler" : "standard";
    if (nextMode === "toddler") {
      router.push("/toddler");
      return;
    }

    setMode("standard");
    setBusyAge(null);
  }

  if (mode === "standard") return <HomeExperience />;

  return (
    <main className="mx-auto grid min-h-screen w-full max-w-6xl content-center gap-7 px-4 py-8">
      <section className="world-entrance grid gap-6 p-5 text-center sm:p-8">
        <div className="relative z-10 mx-auto max-w-3xl">
          <span className="reward-token text-3xl" aria-hidden="true">⭐</span>
          <h1 className="mt-4 text-4xl font-black leading-tight text-ink sm:text-6xl">How old is our little learner?</h1>
          <p className="mt-3 text-xl font-black text-ink/65">Choose one big button.</p>
        </div>
        <div className="relative z-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {ageOptions.map((option) => (
            <button
              key={option.ageGroup}
              type="button"
              disabled={busyAge !== null}
              onClick={() => chooseAge(option.age, option.ageGroup)}
              className="pressable lift-card min-h-44 rounded-[2rem] p-5 text-center text-3xl font-black text-ink disabled:cursor-wait disabled:opacity-70"
            >
              <span className="block text-5xl" aria-hidden="true">{option.label.split(" ")[0]}</span>
              <span className="mt-4 block">{option.label.replace(option.label.split(" ")[0], "").trim()}</span>
              {busyAge === option.age ? <span className="mt-3 block text-base text-leaf">Opening...</span> : null}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
