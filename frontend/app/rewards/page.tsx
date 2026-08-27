"use client";

import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { AppShell } from "@/components/shared/AppShell";
import { NoChildNotice } from "@/components/shared/NoChildNotice";
import { useActiveChild } from "@/lib/useActiveChild";
import { avatarForPage } from "@/services/avatar";
import { getRewards, type BadgeState } from "@/services/rewards";

export default function RewardsPage() {
  const { child, status, error } = useActiveChild();
  const [stars, setStars] = useState<number | null>(null);
  const [badges, setBadges] = useState<BadgeState[]>([]);
  const [loadError, setLoadError] = useState("");
  const { setAvatar } = useAvatar();

  useEffect(() => {
    setAvatar(avatarForPage("rewards"));
  }, [setAvatar]);

  useEffect(() => {
    if (!child) return;
    getRewards(child.child_id)
      .then((summary) => {
        setStars(summary.stars);
        // A server that predates the badge shelf answers with `stars` and
        // `rewards` and no `badges` at all, and `undefined.filter` took the
        // whole screen down. The page shows the stars it did get instead.
        setBadges(summary.badges ?? []);
        setLoadError("");
      })
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : "We could not open the treasure bag.")
      );
  }, [child]);

  const earned = badges.filter((badge) => badge.earned);

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="surface-panel grid gap-5 rounded-[2rem] bg-sunshine p-6 lg:grid-cols-[1fr_12rem] lg:items-center">
          <div>
            <p className="text-sm font-black uppercase text-ink/60">🎁 Treasure Bag</p>
            <h1 className="mt-1 text-5xl font-black text-ink sm:text-6xl">
              {stars ?? 0} ⭐ Stars
            </h1>
            <p className="mt-3 text-xl font-bold text-ink/70">
              {earned.length
                ? `You have collected ${earned.length} ${earned.length === 1 ? "badge" : "badges"} so far.`
                : "Collect stars, badges, medals, and surprise treasures as worlds unlock."}
            </p>
          </div>
          <div className="treasure-chest justify-self-center" />
        </div>

        {status === "loading" ? <p className="font-bold text-ink/60">Loading…</p> : null}
        {status !== "loading" && status !== "ready" ? <NoChildNotice status={status} error={error} /> : null}
        {loadError ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{loadError}</p> : null}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {badges.map((badge) => (
            <div
              key={badge.badge_id}
              className="lift-card grid gap-4 rounded-[2rem] p-6"
              data-earned={badge.earned ? "true" : undefined}
              style={badge.earned ? undefined : { opacity: 0.55 }}
            >
              <span className="reward-token">{badge.earned ? "🏆" : "🔒"}</span>
              <p className="text-xl font-black text-ink">{badge.title}</p>
              <p className="font-bold text-ink/60">
                {badge.earned ? badge.description : badge.progress_hint ?? badge.description}
              </p>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
