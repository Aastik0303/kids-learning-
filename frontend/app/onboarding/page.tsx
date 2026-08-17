"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createChild } from "@/services/child";
import { listClasses } from "@/services/curriculum";
import { getToken } from "@/services/session";
import { LargeButton } from "@/components/shared/LargeButton";
import type { ClassSummary } from "@/types";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

/**
 * Onboarding asks for a birth month once. The class is derived from it on the
 * server, so this form never offers a class picker to the child. The class
 * list is fetched purely so the parent can see which band the answer lands in.
 */
export default function OnboardingPage() {
  const router = useRouter();
  const now = new Date();
  const [name, setName] = useState("");
  const [birthYear, setBirthYear] = useState(now.getFullYear() - 4);
  const [birthMonth, setBirthMonth] = useState(now.getMonth() + 1);
  const [language, setLanguage] = useState("English");
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listClasses()
      .then(setClasses)
      .catch(() => setClasses([]));
  }, []);

  const years = Array.from({ length: 7 }, (_, index) => now.getFullYear() - index);

  // Preview only. The server does this same resolution authoritatively.
  const ageYears = (now.getFullYear() - birthYear) * 12 + (now.getMonth() + 1 - birthMonth);
  const preview = classes.find((item) => ageYears / 12 < item.max_age) ?? classes[classes.length - 1];

  async function submit(event: FormEvent) {
    event.preventDefault();
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }
    try {
      await createChild(token, name.trim() || "Explorer", birthYear, birthMonth, language);
      router.push("/adventure");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Let us try again.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <form onSubmit={submit} className="grid w-full max-w-md gap-4 rounded-[2rem] bg-white p-6 shadow-soft">
        <h1 className="text-3xl font-black">Child profile</h1>

        <label className="grid gap-1 font-bold">
          Name
          <input
            className="rounded-2xl border-2 border-leaf/20 px-4 py-4 font-bold"
            value={name}
            placeholder="Aaru"
            onChange={(e) => setName(e.target.value)}
          />
        </label>

        <fieldset className="grid gap-1">
          <legend className="font-bold">Birth month</legend>
          <div className="grid grid-cols-2 gap-2">
            <select
              aria-label="Birth month"
              className="rounded-2xl border-2 border-leaf/20 px-4 py-4 font-bold"
              value={birthMonth}
              onChange={(e) => setBirthMonth(Number(e.target.value))}
            >
              {MONTHS.map((month, index) => (
                <option key={month} value={index + 1}>
                  {month}
                </option>
              ))}
            </select>
            <select
              aria-label="Birth year"
              className="rounded-2xl border-2 border-leaf/20 px-4 py-4 font-bold"
              value={birthYear}
              onChange={(e) => setBirthYear(Number(e.target.value))}
            >
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>
          <p className="text-sm font-bold text-ink/60">We ask once, then never again.</p>
        </fieldset>

        {preview ? (
          <p data-testid="class-preview" className="rounded-2xl bg-[#f5f8ef] p-4 font-bold">
            Class: {preview.title}
            {preview.subtitle ? ` · ${preview.subtitle}` : ""} (ages {preview.min_age}–{preview.max_age})
          </p>
        ) : null}

        <label className="grid gap-1 font-bold">
          Language
          <select
            className="rounded-2xl border-2 border-leaf/20 px-4 py-4 font-bold"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option>English</option>
          </select>
        </label>

        {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}
        <LargeButton tone="leaf">Start</LargeButton>
      </form>
    </main>
  );
}
