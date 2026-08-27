"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { HomeExperience } from "@/components/home/HomeExperience";
import { useActiveChild } from "@/lib/useActiveChild";

/**
 * The front door, which opens straight into the class.
 *
 * There is one lesson in this app now and the schedule decides what it is, so
 * there is nothing for a child to choose on the way in — a hub screen between
 * them and their class is a place the day quietly ends. Loading the site lands
 * on the AI Teacher, which reads today's frozen plan and starts on the stage the
 * day is pointing at. When the day is done the class says so; that is its answer
 * to give, not this screen's.
 *
 * The old home screen is still what a **guest** sees. Somebody with no child
 * profile has no schedule and therefore no class, and sending them to an empty
 * lesson instead of the sign-up they need would be worse than a hub.
 *
 * Both `/` and `/home` render this, so there is one front door rather than two
 * that can drift apart.
 */
export function FrontDoor() {
  const router = useRouter();
  const { child, status } = useActiveChild();
  const opening = status === "loading" || (status === "ready" && Boolean(child));

  useEffect(() => {
    if (status === "ready" && child) router.replace("/ai-teacher");
  }, [status, child, router]);

  if (opening) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <p role="status" aria-live="polite" className="text-2xl font-black text-ink/60">
          🧑‍🏫 Opening your class…
        </p>
      </main>
    );
  }

  return <HomeExperience />;
}
