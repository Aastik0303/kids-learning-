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
 */
export function ScheduleStrip() {
  const { child } = useActiveChild();
  const { plan, complete } = useTodayPlan(child);

  // Nothing planned is a real answer — a class whose content is still being
  // authored, or a child not signed in yet. An empty strip would only puzzle.
  if (!child || !plan || plan.total === 0) return null;

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
