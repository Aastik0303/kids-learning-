"use client";

import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { AppShell } from "@/components/shared/AppShell";
import { CertificateCard } from "@/components/rewards/CertificateCard";
import { api } from "@/services/api";
import { getChild } from "@/services/session";

type Certificate = {
  unlocked: boolean;
  certificate_id: string | null;
  child_name: string | null;
  completion_date: string | null;
  stars_earned: number;
};

export default function CertificatePage() {
  const [certificate, setCertificate] = useState<Certificate | null>(null);
  const { setAvatar } = useAvatar();

  useEffect(() => {
    setAvatar({
      state: "celebrating",
      message: "The final treasure opens when every world is complete.",
      animationEffect: "certificate_celebration"
    });
    const child = getChild();
    if (!child) return;
    api<Certificate>(`/progress/${child.child_id}/certificate`)
      .then(setCertificate)
      .catch(() => setCertificate(null));
  }, [setAvatar]);

  return (
    <AppShell>
      {certificate?.unlocked && certificate.certificate_id && certificate.child_name && certificate.completion_date ? (
        <div className="grid gap-5">
          <section className="world-entrance grid justify-items-center gap-5 p-6 text-center">
            <div className="treasure-chest mt-8" />
            <div className="relative z-10">
              <p className="text-sm font-black uppercase text-leaf">Final celebration</p>
              <h1 className="mt-2 text-5xl font-black text-ink">Curriculum Complete</h1>
              <p className="mt-3 text-xl font-bold text-ink/70">Every topic in your class is complete.</p>
            </div>
          </section>
          <CertificateCard childName={certificate.child_name} certificateId={certificate.certificate_id} completionDate={certificate.completion_date} stars={certificate.stars_earned} />
          <button className="pressable no-print rounded-3xl bg-leaf px-6 py-4 text-xl font-black text-white shadow-soft" onClick={() => window.print()}>
            Print / Save
          </button>
        </div>
      ) : (
        <section className="surface-panel mx-auto grid max-w-2xl justify-items-center gap-5 rounded-[2rem] p-6 text-center">
          <div className="treasure-chest opacity-70" />
          <h1 className="text-4xl font-black text-ink">Certificate treasure is waiting</h1>
          <p className="text-xl font-bold text-ink/70">Finish every topic in your class to open it.</p>
        </section>
      )}
    </AppShell>
  );
}
