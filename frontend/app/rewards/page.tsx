"use client";

import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { AppShell } from "@/components/shared/AppShell";
import { avatarForPage } from "@/services/avatar";
import { getChild } from "@/services/session";
import type { ChildProfile } from "@/types";

export default function RewardsPage() {
  const [child, setChild] = useState<ChildProfile | null>(null);
  const { setAvatar } = useAvatar();

  useEffect(() => {
    setChild(getChild());
    setAvatar(avatarForPage("rewards"));
  }, [setAvatar]);

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="surface-panel grid gap-5 rounded-[2rem] bg-sunshine p-6 lg:grid-cols-[1fr_12rem] lg:items-center">
          <div>
            <p className="text-sm font-black uppercase text-ink/60">🎁 Treasure Bag</p>
            <h1 className="mt-1 text-5xl font-black text-ink sm:text-6xl">{child?.stars ?? 0} ⭐ Stars</h1>
            <p className="mt-3 text-xl font-bold text-ink/70">Collect stars, badges, medals, and surprise treasures as worlds unlock.</p>
          </div>
          <div className="treasure-chest justify-self-center" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(child?.rewards.length ? child.rewards : ["First badge is waiting"]).map((reward) => (
            <div key={reward} className="lift-card grid gap-4 rounded-[2rem] p-6">
              <span className="reward-token">🏆</span>
              <p className="text-xl font-black text-ink">{reward}</p>
              <p className="font-bold text-ink/60">Collectible reward</p>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
