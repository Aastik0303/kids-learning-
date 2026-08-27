"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shared/AppShell";
import { useActiveChild } from "@/lib/useActiveChild";
import { getToken, getUser, isGuestSession, saveChild } from "@/services/session";
import { updateChildProfile } from "@/services/child";
import { getClassForChild, getClassOptions, setClassOverride } from "@/services/curriculum";
import type { ChildProfile, ClassDetail, ClassSummary } from "@/types";

function progress(child: ChildProfile, subjectId: string, topicCount: number) {
  const done = child.subject_progress?.[subjectId]?.completed_topics.length ?? 0;
  return topicCount ? Math.round((done / topicCount) * 100) : 0;
}

/**
 * The parent surface. Class override lives here and only here: it needs the
 * parent's session token, which the child app never holds, and the server
 * refuses any target that is not adjacent to the child's age-derived class.
 */
export default function ParentProfilePage() {
  const { child, refresh } = useActiveChild();
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [options, setOptions] = useState<ClassSummary[]>([]);
  const [selectedClass, setSelectedClass] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [guest, setGuest] = useState(true);
  const [user, setUser] = useState<ReturnType<typeof getUser>>(null);
  // The child's own details. `PATCH /children/{id}` has always accepted these;
  // nothing in the app ever sent them, so a name typed wrong at onboarding was
  // permanent and a birth month could not be corrected.
  const [name, setName] = useState("");
  const [birthMonth, setBirthMonth] = useState(1);
  const [birthYear, setBirthYear] = useState(new Date().getFullYear());

  useEffect(() => {
    setGuest(isGuestSession());
    setUser(getUser());
  }, []);

  useEffect(() => {
    if (!child) return;
    setSelectedClass(child.class_id);
    setName(child.name);
    setBirthMonth(child.birth_month);
    setBirthYear(child.birth_year);
    getClassForChild(child.child_id).then(setDetail).catch(() => setDetail(null));
    getClassOptions(child.child_id).then(setOptions).catch(() => setOptions([]));
  }, [child]);

  async function applyClass() {
    const token = getToken();
    if (!child || !token) return;
    setError("");
    try {
      const updated = await setClassOverride(child.child_id, token, selectedClass);
      saveChild(updated);
      refresh();
      const next = await getClassForChild(updated.child_id);
      setDetail(next);
      setMessage(
        updated.class_override
          ? `${next.title} is set. You can move back to ${updated.default_class_id} any time.`
          : `${next.title} matches this child's age.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not change the class.");
    }
  }

  async function saveDetails() {
    const token = getToken();
    if (!child || !token) return;
    setError("");
    try {
      const updated = await updateChildProfile(token, child, {
        name: name.trim() || child.name,
        birth_month: birthMonth,
        birth_year: birthYear
      });
      refresh();
      // The birth date decides the class, so the class card is re-read rather
      // than left showing the one the old date implied.
      setDetail(await getClassForChild(updated.child_id));
      setSelectedClass(updated.class_id);
      setMessage("Saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not save those details.");
    }
  }

  return (
    <AppShell>
      <div data-surface="parent">
        {guest ? (
          <section className="surface-panel mx-auto grid max-w-2xl gap-4 rounded-[2rem] p-6 text-center">
            <h1 className="text-4xl font-black text-ink">Parent dashboard is locked</h1>
            <p className="text-xl font-bold text-ink/70">
              Saved progress, rewards and certificates need a parent account.
            </p>
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
              <p className="mt-2 text-xl font-bold text-ink/70">
                Child: {child.name} | Class: {detail?.title ?? child.class_id} | Language: {child.preferred_language}
              </p>
            </div>

            <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
              <div className="surface-panel grid gap-4 rounded-[2rem] p-6">
                <h2 className="text-3xl font-black text-ink">Learning Progress</h2>
                {(detail?.subjects ?? []).map((subject) => {
                  const value = progress(child, subject.subject_id, subject.topic_count);
                  return (
                    <div key={subject.subject_id} className="grid gap-2">
                      <div className="flex justify-between gap-3 font-black text-ink">
                        <span>{subject.title}</span>
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
                  <p className="font-black text-ink/70">Class</p>
                  <p className="text-2xl font-black text-ink">{detail?.title ?? child.class_id}</p>
                  <p className="text-sm font-bold text-ink/60">
                    Set from {child.birth_month}/{child.birth_year}. You can move one class up or down.
                  </p>
                  <label className="grid gap-2 font-black text-ink">
                    Change class
                    <select
                      data-testid="class-override"
                      className="rounded-2xl border-2 border-leaf/20 bg-white px-4 py-4 font-black"
                      value={selectedClass}
                      onChange={(event) => setSelectedClass(event.target.value)}
                    >
                      {options.map((option) => (
                        <option key={option.class_id} value={option.class_id}>
                          {option.title} (ages {option.min_age}–{option.max_age})
                          {option.class_id === child.default_class_id ? " · matches age" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="pressable rounded-3xl bg-leaf px-5 py-4 text-xl font-black text-white shadow-soft"
                    onClick={applyClass}
                  >
                    Apply Class
                  </button>
                  {message ? <p className="rounded-2xl bg-leaf/10 p-3 font-black text-leaf">{message}</p> : null}
                  {error ? <p className="rounded-2xl bg-berry/10 p-3 font-black text-berry">{error}</p> : null}
                </div>
                <div className="lift-card grid gap-3 rounded-[2rem] p-6">
                  <p className="font-black text-ink/70">Child&apos;s details</p>
                  <label className="grid gap-2 font-black text-ink">
                    Name
                    <input
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      className="rounded-2xl border-2 border-leaf/20 bg-white px-4 py-3 font-black"
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="grid gap-2 font-black text-ink">
                      Birth month
                      <input
                        type="number"
                        min={1}
                        max={12}
                        value={birthMonth}
                        onChange={(event) => setBirthMonth(Number(event.target.value))}
                        className="rounded-2xl border-2 border-leaf/20 bg-white px-4 py-3 font-black"
                      />
                    </label>
                    <label className="grid gap-2 font-black text-ink">
                      Birth year
                      <input
                        type="number"
                        min={2015}
                        max={new Date().getFullYear()}
                        value={birthYear}
                        onChange={(event) => setBirthYear(Number(event.target.value))}
                        className="rounded-2xl border-2 border-leaf/20 bg-white px-4 py-3 font-black"
                      />
                    </label>
                  </div>
                  <button
                    type="button"
                    className="pressable rounded-3xl bg-sky px-5 py-4 text-xl font-black text-white shadow-soft"
                    onClick={saveDetails}
                  >
                    Save details
                  </button>
                </div>
                <div className="rounded-[2rem] bg-sunshine p-6 shadow-soft">
                  <p className="font-black text-ink/70">Stars</p>
                  <p className="text-5xl font-black text-ink">{child.stars}</p>
                </div>
                <div className="lift-card rounded-[2rem] p-6">
                  <p className="font-black text-ink/70">Certificate</p>
                  <p className="mt-1 text-2xl font-black text-ink">
                    {child.certificate_unlocked ? "Unlocked" : "Waiting"}
                  </p>
                </div>
              </aside>
            </div>
          </section>
        ) : (
          <p className="font-bold text-ink/60">Let us set up a child profile first.</p>
        )}
      </div>
    </AppShell>
  );
}
