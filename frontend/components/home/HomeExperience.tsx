"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { AppShell } from "@/components/shared/AppShell";
import { avatarForPage } from "@/services/avatar";
import { isSafeGuideTarget, startCompanionSession } from "@/services/companion";
import { useActiveChild } from "@/lib/useActiveChild";
import { isGuestSession } from "@/services/session";
import { getClassForChild } from "@/services/curriculum";
import type { ChildProfile, ClassDetail } from "@/types";

export function HomeExperience() {
  const { child } = useActiveChild();
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [guest, setGuest] = useState(true);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const { setAvatar } = useAvatar();

  useEffect(() => {
    const sync = () => setGuest(isGuestSession());
    sync();
    window.addEventListener("little-learning-session", sync);
    return () => window.removeEventListener("little-learning-session", sync);
  }, []);

  useEffect(() => {
    if (!child) return;
    getClassForChild(child.child_id).then(setDetail).catch(() => setDetail(null));
  }, [child]);

  useEffect(() => {
    if (!child) return;
    let active = true;
    setAvatar(avatarForPage("home"));
    setHighlightId("continue-adventure");
    startCompanionSession(child, guest, "/").then((response) => {
      if (!active) return;
      setAvatar(response.avatar ?? avatarForPage("home"));
      const target = response.guidance?.target_id;
      setHighlightId(isSafeGuideTarget(target) ? target ?? null : null);
    });
    return () => {
      active = false;
    };
  }, [child, guest, setAvatar]);

  // Progress summary is counted from the manifest tree, so it stays right when
  // a subject or topic is added.
  const completedTopics = Object.values(child?.subject_progress ?? {}).reduce(
    (total, progress) => total + progress.completed_topics.length,
    0
  );

  return (
    <AppShell>
      <section className="world-entrance grid content-between gap-6 p-5 sm:p-7">
        <div className="relative z-10 max-w-4xl">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white/80 px-4 py-2 text-sm font-black text-leaf shadow-soft">{guest ? "🎒 Guest Adventure" : "🗺️ Saved Adventure"}</span>
            <span className="rounded-full bg-sunshine px-4 py-2 text-sm font-black text-ink shadow-soft">⭐ Stars {child?.stars ?? 0}</span>
          </div>
          <h1 className="mt-5 max-w-3xl text-5xl font-black leading-tight text-ink sm:text-7xl">Enter the Saksham IQ World</h1>
          <p className="mt-4 max-w-2xl text-xl font-bold text-ink/70">
            Play mini missions, explore magical learning worlds, and collect happy rewards with your guide.
          </p>
        </div>

        <div className="relative z-10 grid gap-4 lg:grid-cols-2">
          <Link
            href="/practice"
            data-guide-id="start-practice"
            className={`adventure-card bg-gradient-to-br from-sky/20 via-white to-sunshine/30 p-6 ${highlightId === "start-practice" ? "guide-glow" : ""}`}
          >
            <div className="grid h-full content-between gap-5">
              <div>
                <span className="reward-token">🎨</span>
                <p className="mt-5 text-sm font-black uppercase text-sky">Practice</p>
                <h2 className="mt-2 text-4xl font-black text-ink sm:text-5xl">Let&apos;s Play & Practice!</h2>
                <p className="mt-3 max-w-md text-lg font-bold text-ink/70">Free play activities drawn from the topics you have already met.</p>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="rounded-full bg-white/80 px-4 py-3 font-black text-ink shadow-soft">🧩 No pressure here</span>
                <span className="pressable rounded-3xl bg-sky px-6 py-4 text-xl font-black text-white shadow-soft">▶️ Start Playing</span>
              </div>
            </div>
          </Link>

          <Link
            href="/adventure"
            data-guide-id="continue-adventure"
            className={`adventure-card bg-gradient-to-br from-leaf/20 via-white to-berry/20 p-6 ${highlightId === "continue-adventure" ? "guide-glow" : ""}`}
          >
            <div className="grid h-full content-between gap-5">
              <div>
                <span className="reward-token">🗺️</span>
                <p className="mt-5 text-sm font-black uppercase text-leaf">Learning Path</p>
                <h2 className="mt-2 text-4xl font-black text-ink sm:text-5xl">Continue Your Adventure</h2>
                <p className="mt-3 max-w-md text-lg font-bold text-ink/70">{detail ? `Explore your ${detail.title} subjects, one topic at a time.` : "Explore your subjects, one topic at a time."}</p>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="rounded-full bg-white/80 px-4 py-3 font-black text-ink shadow-soft">✅ {completedTopics} of {detail?.topic_count ?? 0} topics</span>
                <span className="pressable rounded-3xl bg-leaf px-6 py-4 text-xl font-black text-white shadow-soft">🗺️ Open Map</span>
              </div>
            </div>
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
