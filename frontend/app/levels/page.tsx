"use client";

import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { LearningAdventureMap } from "@/components/learning/LearningAdventureMap";
import { AppShell } from "@/components/shared/AppShell";
import { pathSummaries } from "@/data/prototype";
import { avatarForPage } from "@/services/avatar";
import { listPaths } from "@/services/learning";
import { getOrCreateGuestChild } from "@/services/session";
import type { ChildProfile, PathSummary } from "@/types";

export default function LevelsPage() {
  const [paths, setPaths] = useState<PathSummary[]>(pathSummaries);
  const [child, setChild] = useState<ChildProfile | null>(null);
  const { setAvatar } = useAvatar();

  useEffect(() => {
    const refreshChild = () => setChild(getOrCreateGuestChild());
    refreshChild();
    listPaths().then(setPaths).catch(() => setPaths(pathSummaries));
    window.addEventListener("little-learning-session", refreshChild);
    window.addEventListener("storage", refreshChild);
    return () => {
      window.removeEventListener("little-learning-session", refreshChild);
      window.removeEventListener("storage", refreshChild);
    };
  }, []);

  useEffect(() => {
    setAvatar(avatarForPage("levels"));
  }, [setAvatar]);

  return (
    <AppShell>
      <LearningAdventureMap child={child} paths={paths} />
    </AppShell>
  );
}
