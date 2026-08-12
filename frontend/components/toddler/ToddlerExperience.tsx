"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { ToddlerHome } from "@/components/toddler/ToddlerHome";
import { ToddlerLesson } from "@/components/toddler/ToddlerLesson";
import { guideAgent, progressContext } from "@/services/guide";
import { listToddlerModules } from "@/services/toddler";
import { getOrCreateGuestChild } from "@/services/session";
import type { ChildProfile, ToddlerModule, ToddlerModuleSummary } from "@/types";

export function ToddlerExperience() {
  const router = useRouter();
  const [child, setChild] = useState<ChildProfile | null>(null);
  const [modules, setModules] = useState<ToddlerModuleSummary[]>([]);
  const [activeModule, setActiveModule] = useState<ToddlerModule | null>(null);
  const { setAvatar } = useAvatar();

  useEffect(() => {
    const stored = getOrCreateGuestChild();
    if (stored.age !== null && stored.age !== undefined && stored.age >= 3) {
      router.replace("/");
      return;
    }
    setChild(stored);
    listToddlerModules().then(setModules);
    setAvatar({ state: "waving", message: "Getting your little lessons ready...", speak: false, animationEffect: "none" });
    guideAgent({
      session_id: `toddler_home_${stored.child_id}`,
      child_id: stored.child_id,
      mode: "welcome",
      event: "HOME_OPENED",
      route: "/toddler",
      screen: "toddler_home",
      feature: "toddler_modules",
      age_group: stored.age_group,
      age: stored.age,
      learning_mode: "toddler",
      preferred_language: stored.preferred_language,
      toddler: { learning_mode: "toddler", age: stored.age, stars: stored.stars },
      progress: progressContext(stored, "toddler"),
      available_actions: ["highlight"],
      available_targets: ["toddler-module-alphabets", "toddler-module-numbers", "toddler-module-colours", "toddler-module-shapes"]
    }).then((guide) => setAvatar(guide.avatar));
  }, [router, setAvatar]);

  if (!child) {
    return <main className="grid min-h-screen place-items-center text-3xl font-black text-ink">Opening...</main>;
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-4 py-5 pb-8">
      {activeModule ? (
        <ToddlerLesson child={child} module={activeModule} onHome={() => setActiveModule(null)} onChildChange={setChild} />
      ) : (
        <ToddlerHome stars={child.stars} modules={modules} onStart={setActiveModule} />
      )}
    </main>
  );
}
