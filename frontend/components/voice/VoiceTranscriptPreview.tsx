"use client";

export function VoiceTranscriptPreview({ transcript }: { transcript?: string | null }) {
  if (!transcript) return null;

  return (
    <div className="rounded-3xl border border-sky/15 bg-[#f7fbff] px-4 py-3 text-center">
      <p className="text-xs font-black uppercase text-sky">I heard</p>
      <p className="mt-1 text-2xl font-black text-ink">{transcript}</p>
    </div>
  );
}
