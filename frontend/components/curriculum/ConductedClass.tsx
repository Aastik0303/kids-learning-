"use client";

import { useCallback, useState, type ReactNode } from "react";
import Link from "next/link";

import { ActivityView } from "@/components/curriculum/ActivityView";
import { AppShell } from "@/components/shared/AppShell";
import { NoChildNotice } from "@/components/shared/NoChildNotice";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { FALLBACK_MODE } from "@/lib/experience";
import { useActiveChild } from "@/lib/useActiveChild";
import { useConductorClass, type ClassSummary } from "@/lib/useConductorClass";
import { announcePlanChanged } from "@/lib/useTodayPlan";
import { isTextToken, visualIcon } from "@/lib/visualIcon";
import { getProgress } from "@/services/child";
import { saveChild } from "@/services/session";

/**
 * One sitting of the conducted class, wherever it was opened from.
 *
 * **Nothing in the web app mounts this any more.** The class is the AI Teacher:
 * it runs one stage per item of today's frozen plan and it is the only thing
 * that marks a level done. `/class` redirects to it and Adventure teaches
 * nothing, so this component and `useConductorClass` are left here unwired
 * rather than deleted — the `/conductor` endpoints behind them are untouched and
 * still serve the mobile app.
 *
 * This used to be the body of `/class` alone, while Adventure ran a second
 * teaching loop of its own over `/learning` — which is why a letter explained
 * on the Adventure map went straight to a question with no microphone in
 * between. There is one loop now, and both routes render it.
 *
 * The beat this exists for is `say_it`. Once the guide has explained a letter —
 * "This is अ. अ is for अनार." — the class stops and asks for it back, the
 * microphone opens **by itself**, and what the child says decides whether the
 * next thing is the drawing or a second, differently-worded explanation from
 * the learned policy. Nothing here judges what was said; the server does,
 * deterministically, and never scores it.
 */
export function ConductedClass({
  topicId = null,
  header = null,
  renderComplete
}: {
  /** A level picked off the Adventure map. Null means today's own class. */
  topicId?: string | null;
  /** Shown above the class: the level title and what it is about. */
  header?: ReactNode;
  /** What the finished screen offers next. Defaults to going home. */
  renderComplete?: (summary: ClassSummary) => ReactNode;
}) {
  const { child, status, error: childError } = useActiveChild();
  const { setAvatar } = useAvatar();
  const [summary, setSummary] = useState<ClassSummary | null>(null);

  const onComplete = useCallback(
    (finished: ClassSummary) => {
      setSummary(finished);
      setAvatar({ state: "celebrating", message: "", animationEffect: "star_burst", durationMs: 3000 });
      // The stars and the unlock happened on the server. The stored child is a
      // snapshot from before this sitting, so without refreshing it the header
      // still shows the old star count and the schedule strip still shows the
      // lesson that was current a moment ago.
      if (!child) return;
      getProgress(child.child_id)
        .then((refreshed) => {
          saveChild(refreshed.child);
          announcePlanChanged();
        })
        .catch(() => {
          // A stale star count is not worth interrupting a celebration for.
        });
    },
    [child, setAvatar]
  );

  const { directive, loading, busy, error, notToday, listening, answer, speakAnswer, repeat, raiseHand } =
    useConductorClass({ childId: child?.child_id ?? null, topicId, onComplete });

  if (status !== "loading" && status !== "ready") {
    return (
      <AppShell>
        <NoChildNotice status={status} error={childError} />
      </AppShell>
    );
  }

  if (notToday) {
    // The schedule doing its job, not a failure: this level is unlocked and
    // waiting for the day the plan gives it. Said in the server's own words,
    // with a way back to what today actually holds.
    return (
      <AppShell>
        <section className="surface-panel grid gap-4 rounded-[2rem] p-6 text-center">
          <p className="text-5xl" aria-hidden>
            🌙
          </p>
          <h1 className="text-xl font-black text-ink sm:text-2xl">{notToday}</h1>
          <Link
            href="/"
            className="pressable mx-auto rounded-3xl bg-leaf px-6 py-4 text-lg font-black text-white shadow-soft"
          >
            🗓️ See today&apos;s plan
          </Link>
        </section>
      </AppShell>
    );
  }

  if (summary) {
    return (
      <AppShell>
        <section className="surface-panel grid gap-5 rounded-[2rem] p-6 text-center">
          <p className="text-6xl" aria-hidden>
            🎉
          </p>
          <h1 className="text-4xl font-black text-ink">You did it!</h1>
          <p className="text-xl font-bold text-ink/70">{closingLine(summary.reason)}</p>
          {summary.starsEarned > 0 ? (
            <p className="text-2xl font-black text-sunshine">⭐ {summary.starsEarned}</p>
          ) : null}
          {/* No "play the next level" button. When the next one is played is the
              frozen daily plan's decision, not a button's. */}
          {renderComplete ? (
            renderComplete(summary)
          ) : (
            <Link
              href="/"
              className="pressable mx-auto rounded-full bg-sky px-6 py-4 text-lg font-black text-white shadow-soft"
            >
              🏠 Back home
            </Link>
          )}
        </section>
      </AppShell>
    );
  }

  if (loading || !directive) {
    return (
      <AppShell>
        <div className="grid gap-5">
          {header}
          <p className="surface-panel rounded-[2rem] p-6 text-xl font-black text-ink/60">
            Getting your class ready…
          </p>
        </div>
      </AppShell>
    );
  }

  const { listen, speech, scaffold, activity, progress } = directive;

  return (
    <AppShell>
      <section className="grid gap-5">
        {header}

        {progress.total > 0 ? (
          <div className="surface-panel rounded-[2rem] p-4">
            <p className="text-sm font-black uppercase text-sky">Today&apos;s class</p>
            <div className="mt-2 h-3 overflow-hidden rounded-full bg-ink/10">
              <div
                className="h-full rounded-full bg-leaf transition-all"
                style={{ width: `${Math.min((progress.filled / progress.total) * 100, 100)}%` }}
              />
            </div>
          </div>
        ) : null}

        {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}

        {/* What the guide is saying, on screen as well as aloud. A pre-reader
            does not read it; the grown-up beside them does, and it is what
            makes the class followable with the sound off. */}
        <section
          aria-live="polite"
          className="surface-panel grid gap-3 rounded-[2rem] p-5"
          data-testid={`class-phase-${directive.phase}`}
        >
          <div className="flex items-start gap-3">
            <span aria-hidden className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-sky/10 text-3xl">
              🦉
            </span>
            <div className="min-w-0">
              <p className="text-xs font-black uppercase tracking-wide text-sky">Your guide</p>
              <p className="text-lg font-black leading-snug text-ink sm:text-xl">{speech.text}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void repeat()}
              className="pressable rounded-full bg-white px-5 py-3 text-base font-black text-ink shadow-soft"
            >
              🔊 Say it again
            </button>
            {/* Raising a hand is an input like any other: the server stops the
                class kindly and keeps the place, so a child who has had enough
                is never left tapping through to the end of a lesson. */}
            <button
              type="button"
              onClick={raiseHand}
              disabled={busy}
              className="pressable rounded-full bg-white px-5 py-3 text-base font-black text-ink shadow-soft disabled:opacity-50"
            >
              ✋ I need a break
            </button>
          </div>
        </section>

        {/* The listening beat. The microphone is already open by the time this
            renders — the button is here so a child who stayed quiet can start it
            again, not so they can start it in the first place. */}
        {listen.active ? (
          <section className="surface-panel grid justify-items-center gap-4 rounded-[2rem] p-6">
            {listen.expect ? (
              <p
                className="rounded-3xl bg-sunshine/25 px-10 py-6 text-6xl font-black text-ink"
                lang={isTextToken(listen.expect) ? undefined : "hi"}
              >
                {isTextToken(listen.expect) ? listen.expect : visualIcon(listen.expect)}
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => void speakAnswer()}
              disabled={busy || listening}
              aria-label={listening ? "Listening" : "Tap and say it"}
              className={`pressable grid h-32 w-32 place-items-center rounded-full text-5xl shadow-soft disabled:opacity-70 ${
                listening ? "animate-pulse bg-leaf text-white" : "bg-sunshine text-ink"
              }`}
            >
              🎤
            </button>
            <p className="text-lg font-bold text-ink/70">
              {listening ? "I am listening…" : "Say it out loud!"}
            </p>
          </section>
        ) : null}

        {activity ? (
          <ActivityView
            activity={{
              ...activity,
              options: scaffold.options_shown.length ? scaffold.options_shown : activity.options
            }}
            mode={FALLBACK_MODE}
            sessionId={directive.session_id}
            onAnswer={answer}
            // Locked while the guide is talking or the class is listening, so a
            // stray tap cannot answer a question that has not been asked yet.
            disabled={busy || listen.active}
            guideMessage=""
            visualAction={directive.visual_action}
          />
        ) : null}
      </section>
    </AppShell>
  );
}

/** What the class's own ending says, in words a grown-up can read out. */
function closingLine(reason: string): string {
  if (reason === "day_complete") return "That is everything for today. See you tomorrow!";
  if (reason === "end_kindly") return "We stopped for now — that is completely fine.";
  return "Today's class is finished.";
}
