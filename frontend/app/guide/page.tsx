"use client";

import { FormEvent, useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { AppShell } from "@/components/shared/AppShell";
import { guideAnswer } from "@/data/prototype";
import { avatarForPage } from "@/services/avatar";
import { GUIDE_TARGETS, guideAgent } from "@/services/guide";
import { getOrCreateGuestChild } from "@/services/session";

export default function GuidePage() {
  const [question, setQuestion] = useState("How do I start the numbers level?");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const { setAvatar } = useAvatar();

  useEffect(() => {
    setAvatar(avatarForPage("guide"));
  }, [setAvatar]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    const instantAnswer = guideAnswer(question);
    setAnswer(instantAnswer);
    setAvatar({ state: "speaking", message: instantAnswer, speak: true, animationEffect: "none", durationMs: null });
    const child = getOrCreateGuestChild();
    try {
      const result = await guideAgent({
        session_id: `guide_${Date.now()}`,
        child_id: child.child_id,
        mode: question.toLowerCase().includes("parent") ? "parent_help" : "help",
        event: "GUIDE_HELP_REQUESTED",
        route: "/guide",
        screen: "guide_help",
        feature: question || "help",
        age_group: child.age_group,
        preferred_language: child.preferred_language,
        progress: {
          current_world: child.current_path,
          current_level: `Level ${child.current_stage}`,
          last_completed_level: null,
          weak_skills: child.weak_skills,
          session_stars: child.stars
        },
        available_actions: ["highlight", "show_tooltip"],
        available_targets: [GUIDE_TARGETS.CONTINUE_ADVENTURE, GUIDE_TARGETS.HOME_PRACTICE, GUIDE_TARGETS.REWARDS_BUTTON, GUIDE_TARGETS.ASK_GUIDE]
      });
      if (result.message !== instantAnswer) {
        setAnswer(result.message);
        setAvatar({ ...(result.avatar ?? { state: "speaking", message: result.message, animationEffect: "none" }), speak: true });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <form onSubmit={submit} className="surface-panel mx-auto grid w-full max-w-3xl gap-5 rounded-[2rem] p-6">
        <div>
          <p className="text-sm font-black uppercase text-berry">Learning helpers</p>
          <h1 className="mt-1 text-4xl font-black text-ink sm:text-5xl">Little Learning Guide</h1>
        </div>
        <div className="grid gap-3 rounded-[2rem] bg-[#f7fbff] p-4">
          <input className="min-h-16 rounded-3xl border-2 border-leaf/20 bg-white px-5 py-4 text-lg font-bold shadow-soft" value={question} onChange={(e) => setQuestion(e.target.value)} />
          <button disabled={busy} className="pressable rounded-3xl bg-berry px-6 py-4 text-xl font-black text-white shadow-soft disabled:opacity-60">Ask</button>
        </div>
        {answer ? <p className="lift-card rounded-[2rem] bg-[#eef8f2] p-5 text-xl font-bold text-ink">{answer}</p> : null}
      </form>
    </AppShell>
  );
}
