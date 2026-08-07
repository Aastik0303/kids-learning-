"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/shared/AppShell";
import { getOrCreateGuestChild, isGuestSession } from "@/services/session";
import { practiceCards, pathAccents } from "@/data/prototype";

export default function PracticePage() {
  const [guest, setGuest] = useState(true);

  useEffect(() => {
    getOrCreateGuestChild();
    setGuest(isGuestSession());
  }, []);

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="surface-panel flex flex-wrap items-end justify-between gap-3 rounded-[2rem] p-5">
          <div>
            <p className="text-sm font-black uppercase text-sky">Practice</p>
            <h1 className="text-4xl font-black text-ink sm:text-5xl">Choose a quick activity</h1>
          </div>
          <Link className="pressable rounded-full bg-white px-4 py-3 font-black text-ink shadow-soft" href="/">
            Back Home
          </Link>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {practiceCards.map((card, index) => {
            const key = card.topic === "mixed" ? "mixed_final" : card.topic;
            return (
              <Link
                key={card.topic}
                href={`/practice/${card.topic}`}
                data-guide-id={index === 0 ? "start-practice" : undefined}
                className={`lift-card grid min-h-72 content-between gap-5 rounded-[2rem] p-6 ${index === 0 ? "border-sky ring-4 ring-sky/10" : ""}`}
              >
                <div className="grid gap-3">
                  <span className={`grid h-20 w-20 place-items-center rounded-[1.75rem] text-2xl font-black shadow-soft ${pathAccents[key].tone}`}>{card.icon}</span>
                  <div>
                    <span className="rounded-full bg-[#f5f8ef] px-3 py-1 text-xs font-black text-ink">{guest ? "Guest" : "Free practice"}</span>
                    <h2 className="mt-3 text-3xl font-black text-ink">{card.title}</h2>
                    <p className="mt-2 text-lg font-bold text-ink/70">{card.description}</p>
                  </div>
                </div>
                <div className="grid gap-2">
                  <p className="font-black text-berry">Practice only</p>
                  <span className="pressable rounded-3xl bg-sunshine px-5 py-4 text-center text-xl font-black text-ink shadow-soft">Start Practice</span>
                </div>
              </Link>
            );
          })}
        </div>
      </section>
    </AppShell>
  );
}
