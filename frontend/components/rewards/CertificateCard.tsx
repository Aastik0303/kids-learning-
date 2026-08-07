"use client";

export function CertificateCard({
  childName,
  certificateId,
  completionDate,
  stars
}: {
  childName: string;
  certificateId: string;
  completionDate: string;
  stars: number;
}) {
  return (
    <section className="mx-auto grid max-w-3xl gap-5 border-8 border-sunshine bg-white p-8 text-center shadow-soft">
      <p className="text-lg font-bold text-leaf">Little Learning Explorer Certificate</p>
      <h1 className="text-4xl font-black text-ink">{childName}</h1>
      <p className="text-xl font-bold">Completed the AI Nursery Learning Path</p>
      <p className="text-lg">Numbers, letters, colours, and shapes</p>
      <p className="rounded-3xl bg-[#eef8f2] p-4 font-black">Stars earned: {stars}</p>
      <p className="text-sm font-bold text-ink/70">
        {certificateId} | {completionDate}
      </p>
    </section>
  );
}
