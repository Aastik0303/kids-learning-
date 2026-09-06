"use client";

import { useActiveChild } from "@/lib/useActiveChild";
import { useTodayPlan } from "@/lib/useTodayPlan";

/**
 * Today's schedule, on every screen.
 *
 * The plan is the day's work and the class is built out of it: one stage per
 * planned item, and when the last one is through the day is shut until
 * tomorrow. A rule that shapes the whole sitting cannot live behind a chip the
 * child has to know to tap, so this rides in the shell above every page — the
 * class, the Adventure map, the rewards shelf — and says the same thing on all
 * of them.
 *
 * It is deliberately not a menu. Nothing here is tappable: the class opens the
 * next stage by itself and Adventure teaches nothing any more, so a link would
 * only offer a child a door that does not exist. This says where the day is,
 * and that is all it says.
 *
 * A day has two halves and this shows both. The 🧩 chips are the **retention
 * check-ins** the scheduler says are due — something taught two days ago, asked
 * again before today's first stage. They come first because that is the order
 * the class asks them in, and they are not counted in the "3/5" on the right:
 * a check-in is not one of the day's levels, it teaches nothing, and answering
 * it moves neither the count nor a star.
 */
export function ScheduleStrip() {
  const { child } = useActiveChild();
  const { plan, complete, retentionTests } = useTodayPlan(child);

  // Nothing planned is a real answer — a class whose content is still being
  // authored, or a child not signed in yet. An empty strip would only puzzle.
  // A day with no levels left can still owe a check-in, so both halves of the
  // schedule are asked before the strip gives up on drawing anything.
  if (!child || !plan || (plan.total === 0 && retentionTests.length === 0)) return null;

  return (
    <section
      aria-label="Today's schedule"
      data-testid="schedule-strip"
      className="no-print mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-[1.75rem] bg-white/85 px-4 py-3 shadow-soft backdrop-blur"
    >
      <span className="text-sm font-black uppercase tracking-wide text-leaf">
        {complete ? "🎉 Today" : "🗓️ Today"}
      </span>

      <ol className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        {/*
          The check-ins first, because that is the order the class asks them in:
          something taught two days ago is remembered before today's new thing
          is taught. They are a different shape from a level chip on purpose —
          no number, no tick — because they are not one of the day's stages and
          nothing about answering one moves the count on the right.
        */}
        {retentionTests.map((test) => (
          <li
            key={test.test_id}
            data-testid="schedule-retention"
            data-topic-id={test.topic_id}
            data-state="check-in"
            title={`We will remember ${test.title} before today's lessons`}
            className="flex items-center gap-1.5 rounded-full bg-sky/15 px-3 py-1.5 text-sm font-bold text-sky"
          >
            <span aria-hidden>🧩</span>
            <span className="max-w-[10rem] truncate">{test.title}</span>
          </li>
        ))}

        {plan.items.map((item, index) => (
          <li
            key={item.topic_id}
            data-topic-id={item.topic_id}
            data-state={item.done ? "done" : item.current ? "now" : "waiting"}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-bold ${
              item.done
                ? "bg-leaf/15 text-leaf"
                : item.current
                  ? "bg-sunshine text-ink"
                  : "bg-ink/5 text-ink/50"
            }`}
          >
            <span aria-hidden>{item.done ? "✅" : item.current ? "▶️" : index + 1}</span>
            <span className="max-w-[10rem] truncate">{item.title}</span>
          </li>
        ))}
      </ol>

      <span className="text-sm font-black text-ink/60">
        {plan.completed}/{plan.total}
      </span>

      {complete ? (
        // The day being finished is something to be pleased about, and the next
        // one opening tomorrow is the good news rather than a door closing. The
        // server says the same thing when the class is asked.
        <span className="rounded-full bg-leaf/10 px-3 py-1.5 text-sm font-black text-leaf">
          All done — the next one is tomorrow
        </span>
      ) : null}
    </section>
  );
}
