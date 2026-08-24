"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useActiveChild } from "@/lib/useActiveChild";
import { useTodayPlan } from "@/lib/useTodayPlan";
import { subjectOf } from "@/services/plan";

/**
 * The app opening today's lesson by itself, for the children who cannot.
 *
 * A two-year-old cannot navigate. Every tap between them and their lesson is a
 * place the day quietly ends - a subject card, a level, a "start" - and the
 * child who gives up at one of them is not a child who chose not to learn.
 *
 * So for Play Group and Nursery the home screen counts down and opens today's
 * planned lesson. Three things keep that from being a trap:
 *
 * - **The server decides who this is for.** `plan.autopilot` is true only for
 *   `early` experience mode and only while the day still has work in it. From
 *   LKG the child chooses, and taking that away would be worse than the taps.
 * - **A grown-up can always stop it**, and stopping it lasts for this visit
 *   rather than for ever - a parent who wants a minute on the home screen gets
 *   it, and tomorrow starts fresh.
 * - **The countdown is the tap.** Browsers refuse to speak until a real gesture
 *   has happened, so "Start now" doubles as the gesture that lets the guide's
 *   voice work for the rest of the sitting.
 */

const COUNTDOWN_SECONDS = 4;

/** Per visit, not per day: a pause is "not right now", not "never again". */
const PAUSE_KEY = "saksham.autopilot.paused";

function readPaused(): boolean {
  try {
    return window.sessionStorage.getItem(PAUSE_KEY) === "1";
  } catch {
    return false;
  }
}

function writePaused(paused: boolean) {
  try {
    window.sessionStorage.setItem(PAUSE_KEY, paused ? "1" : "0");
  } catch {
    // A browser that will not remember this is not a reason to fail.
  }
}

export function AutoOpenGate() {
  const router = useRouter();
  const { child } = useActiveChild();
  const { autopilot, current } = useTodayPlan(child);
  const [paused, setPaused] = useState(true);
  const [left, setLeft] = useState(COUNTDOWN_SECONDS);

  // Starts paused until the browser can be asked, so nothing counts down during
  // the first render on a device where the grown-up already said no.
  useEffect(() => {
    setPaused(readPaused());
  }, []);

  const subjectId = current ? subjectOf(current.skill_id) : null;
  const href = subjectId && current ? `/adventure/${subjectId}/${current.topic_id}` : null;
  const running = autopilot && Boolean(href) && !paused;

  useEffect(() => {
    if (!running) return;
    if (left <= 0) {
      router.push(href as string);
      return;
    }
    const timer = window.setTimeout(() => setLeft((seconds) => seconds - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [running, left, href, router]);

  if (!autopilot || !current || !href) return null;

  const stop = () => {
    setPaused(true);
    writePaused(true);
  };

  const startNow = () => {
    writePaused(false);
    router.push(href);
  };

  return (
    <section
      role="status"
      aria-live="polite"
      data-testid="auto-open-gate"
      className="mb-5 grid gap-3 rounded-3xl bg-white/90 p-5 shadow-soft sm:flex sm:items-center sm:justify-between sm:gap-6"
    >
      <div className="grid gap-1">
        <p className="text-sm font-black uppercase tracking-wide text-leaf">🎈 Today&apos;s lesson</p>
        <p className="text-2xl font-black leading-tight text-ink">{current.title}</p>
        <p className="font-bold text-ink/60">
          {paused ? "Ready when you are." : `Starting in ${left}...`}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={startNow}
          data-guide-id="continue-adventure"
          className="pressable rounded-3xl bg-leaf px-6 py-4 text-lg font-black text-white shadow-soft"
        >
          ▶️ Start now
        </button>
        {paused ? null : (
          <button
            type="button"
            onClick={stop}
            className="pressable rounded-3xl bg-white px-5 py-4 text-lg font-black text-ink shadow-soft"
          >
            ✋ Wait
          </button>
        )}
      </div>
    </section>
  );
}
