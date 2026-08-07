"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { AppShell } from "@/components/shared/AppShell";
import { avatarForPage } from "@/services/avatar";
import { isSafeGuideTarget, startCompanionSession } from "@/services/companion";
import { getOrCreateGuestChild, isGuestSession } from "@/services/session";
import type { ChildProfile } from "@/types";

export function HomeExperience() {
  const [child, setChild] = useState<ChildProfile | null>(null);
  const [guest, setGuest] = useState(true);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const { setAvatar } = useAvatar();

  useEffect(() => {
    const sync = () => {
      setChild(getOrCreateGuestChild());
      setGuest(isGuestSession());
    };
    sync();
    window.addEventListener("little-learning-session", sync);
    return () => window.removeEventListener("little-learning-session", sync);
  }, []);

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

  const numbersProgress = child?.path_progress.numbers.completed_stages.length ?? 0;

  return (
    <AppShell>
      <section className="world-entrance grid content-between gap-6 p-5 sm:p-7">
        <div className="relative z-10 max-w-4xl">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white/80 px-4 py-2 text-sm font-black text-leaf shadow-soft">{guest ? "🎒 Guest Adventure" : "🗺️ Saved Adventure"}</span>
            <span className="rounded-full bg-sunshine px-4 py-2 text-sm font-black text-ink shadow-soft">⭐ Stars {child?.stars ?? 0}</span>
          </div>
          <h1 className="mt-5 max-w-3xl text-5xl font-black leading-tight text-ink sm:text-7xl">Enter the Little Learning World</h1>
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
                <p className="mt-3 max-w-md text-lg font-bold text-ink/70">Free play activities for numbers, ABC, colours, shapes, and mixed review.</p>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="rounded-full bg-white/80 px-4 py-3 font-black text-ink shadow-soft">🧩 No stages here</span>
                <span className="pressable rounded-3xl bg-sky px-6 py-4 text-xl font-black text-white shadow-soft">▶️ Start Playing</span>
              </div>
            </div>
          </Link>

          <Link
            href="/levels"
            data-guide-id="continue-adventure"
            className={`adventure-card bg-gradient-to-br from-leaf/20 via-white to-berry/20 p-6 ${highlightId === "continue-adventure" ? "guide-glow" : ""}`}
          >
            <div className="grid h-full content-between gap-5">
              <div>
                <span className="reward-token">🗺️</span>
                <p className="mt-5 text-sm font-black uppercase text-leaf">Learning Path</p>
                <h2 className="mt-2 text-4xl font-black text-ink sm:text-5xl">Continue Your Adventure</h2>
                <p className="mt-3 max-w-md text-lg font-bold text-ink/70">Travel through Number Kingdom, Alphabet Forest, Colour Garden, Shape Island, and the Magic Castle.</p>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="rounded-full bg-white/80 px-4 py-3 font-black text-ink shadow-soft">🔢 Numbers {numbersProgress} of 8</span>
                <span className="pressable rounded-3xl bg-leaf px-6 py-4 text-xl font-black text-white shadow-soft">🗺️ Open Map</span>
              </div>
            </div>
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
