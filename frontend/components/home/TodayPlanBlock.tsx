"use client";

import Link from "next/link";
import { useState } from "react";
import { useActiveChild } from "@/lib/useActiveChild";
import { useTodayPlan } from "@/lib/useTodayPlan";
import { subjectOf } from "@/services/plan";

/**
 * Today's schedule, as a chip in the app bar.
 *
 * The plan is the day's work, not a suggestion: the server refuses a topic the
 * day does not hold, and the topic map draws those as sleeping. So it belongs
 * where a child and the grown-up beside them can always find it - the header,
 * which is on every screen - rather than on the home page alone.
 *
 * It was briefly a floating ball in the corner. A chip is better: it sits in the
 * row the child already reads for their stars and their saved adventure, it
 * cannot drift over an activity, and it needs no rule about which routes to
 * hide on. The panel opens only when it is asked for, so nothing ever covers a
 * lesson in progress.
 */

const REASON_LABEL: Record<string, string> = {
  new: "New",
  revisit: "Again",
  prerequisite: "First step"
};

export function TodayPlanChip() {
  const { child } = useActiveChild();
  const { plan, complete } = useTodayPlan(child);
  const [open, setOpen] = useState(false);

  // Nothing planned is a real answer - a class whose content is still being
  // authored, or a child not signed in yet. An empty chip would only puzzle.
  if (!child || !plan || plan.total === 0) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        aria-expanded={open}
        aria-label={`Today's plan. ${plan.completed} of ${plan.total} done.`}
        data-testid="today-plan-chip"
        data-guide-id="today-plan"
        className={`pressable rounded-full px-4 py-3 text-sm font-black shadow-soft ${
          complete ? "bg-leaf text-white" : "bg-white text-ink"
        }`}
      >
        <span aria-hidden>{complete ? "🎉" : "🗓️"}</span>{" "}
        {plan.completed}/{plan.total}
      </button>

      {open ? (
        <>
          {/* Tapping anywhere else closes it, the same way the parent drawer
              behaves. A child who opens this by accident must not be stuck. */}
          <button
            type="button"
            aria-label="Close today's plan"
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />
          <section
            aria-label="Today's plan"
            className="fixed right-3 top-24 z-40 max-h-[70vh] w-[min(20rem,calc(100vw-1.5rem))] overflow-y-auto rounded-3xl bg-white/95 p-4 shadow-soft backdrop-blur sm:right-6"
          >
            <header className="flex items-center justify-between gap-2">
              <div>
                <p className="text-xs font-black uppercase tracking-wide text-leaf">🗓️ Today</p>
                <p className="text-sm font-bold text-ink/60">
                  {plan.completed} of {plan.total} done
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close today's plan"
                className="pressable grid h-8 w-8 place-items-center rounded-full bg-ink/5 text-lg font-black text-ink/60 hover:bg-ink/10"
              >
                ×
              </button>
            </header>

            <ol className="mt-3 grid gap-2">
              {plan.items.map((item) => {
                const subjectId = subjectOf(item.skill_id);
                const label = (
                  <span className="flex items-center gap-2">
                    <span aria-hidden>{item.done ? "✅" : item.current ? "▶️" : "•"}</span>
                    <span
                      className={`text-sm font-bold ${item.done ? "text-ink/40 line-through" : "text-ink"}`}
                    >
                      {item.title}
                    </span>
                    {item.reason !== "new" ? (
                      <span className="rounded-full bg-sunshine/40 px-2 py-0.5 text-[10px] font-black uppercase text-ink/70">
                        {REASON_LABEL[item.reason] ?? item.reason}
                      </span>
                    ) : null}
                  </span>
                );

                return (
                  <li key={item.topic_id}>
                    {subjectId && !item.done ? (
                      <Link
                        href={`/adventure/${subjectId}/${item.topic_id}`}
                        onClick={() => setOpen(false)}
                        className={`block rounded-2xl px-2 py-2 transition ${
                          item.current ? "bg-leaf/10" : "hover:bg-ink/5"
                        }`}
                      >
                        {label}
                      </Link>
                    ) : (
                      <div className="rounded-2xl px-2 py-2">{label}</div>
                    )}
                  </li>
                );
              })}
            </ol>

            {complete ? (
              // The day being finished is something to be pleased about, and the
              // next level opening tomorrow is the good news rather than a door
              // closing. The server says the same thing when it is asked.
              <p className="mt-3 rounded-2xl bg-leaf/10 px-3 py-2 text-sm font-black text-leaf">
                🎉 All done for today! The next one opens tomorrow.
              </p>
            ) : null}

            {plan.source === "planner_agent" ? (
              <p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-ink/35">
                Planned for you
              </p>
            ) : null}
          </section>
        </>
      ) : null}
    </>
  );
}
