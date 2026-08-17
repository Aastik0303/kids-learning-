"use client";

import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { SubjectGrid } from "@/components/curriculum/SubjectGrid";
import { AppShell } from "@/components/shared/AppShell";
import { NoChildNotice } from "@/components/shared/NoChildNotice";
import { useActiveChild } from "@/lib/useActiveChild";
import { avatarForPage } from "@/services/avatar";
import { getClassForChild } from "@/services/curriculum";
import type { ClassDetail } from "@/types";

export default function AdventurePage() {
  const { child, status, error } = useActiveChild();
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [loadError, setLoadError] = useState("");
  const { setAvatar } = useAvatar();

  useEffect(() => {
    if (!child) return;
    getClassForChild(child.child_id)
      .then((next) => {
        setDetail(next);
        setLoadError("");
      })
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : "We could not load your subjects.")
      );
  }, [child]);

  useEffect(() => {
    setAvatar(avatarForPage("levels"));
  }, [setAvatar]);

  return (
    <AppShell>
      {status === "loading" ? <p className="font-bold text-ink/60">Getting your subjects ready…</p> : null}
      {status !== "loading" && status !== "ready" ? <NoChildNotice status={status} error={error} /> : null}
      {loadError ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{loadError}</p> : null}
      {detail ? <SubjectGrid detail={detail} child={child} /> : null}
    </AppShell>
  );
}
