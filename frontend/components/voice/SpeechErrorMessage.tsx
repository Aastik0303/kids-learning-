"use client";

export function SpeechErrorMessage({ message }: { message?: string | null }) {
  if (!message) return null;

  return (
    <p className="rounded-3xl bg-berry/10 px-4 py-3 text-center text-base font-black text-berry" role="status">
      {message}
    </p>
  );
}
