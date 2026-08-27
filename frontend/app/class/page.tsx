"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * `/class` is the AI Teacher now.
 *
 * This route used to render the conductor's own sitting, which was a second
 * teaching loop beside the AI Teacher's: two schedules, two ideas of what
 * "today" meant, and two places a level could be marked done. The class is the
 * AI Teacher — it runs one stage per item of today's frozen plan and shuts the
 * day when the last one is through — so this URL keeps working and goes there.
 *
 * The conductor itself is untouched and `/conductor/...` still serves the mobile
 * app; what has gone is the web app's second front end onto it.
 */
export default function ClassPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/ai-teacher");
  }, [router]);

  return (
    <main className="grid min-h-screen place-items-center px-6">
      <p role="status" aria-live="polite" className="text-2xl font-black text-ink/60">
        🧑‍🏫 Opening your class…
      </p>
    </main>
  );
}
