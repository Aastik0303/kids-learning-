import type { ExperienceMode } from "@/types";
import { showsText } from "@/lib/experience";

type Props = {
  title: string;
  mode: ExperienceMode;
};

/**
 * An honest empty state for a subject or topic whose activities are not
 * authored yet. It is never a crash and never a blank screen: the child sees
 * that this part of the curriculum exists and is being made.
 */
export function ComingSoon({ title, mode }: Props) {
  return (
    <div
      role="status"
      data-testid="coming-soon"
      className="grid gap-2 rounded-[2rem] bg-[#f5f8ef] p-6 text-center"
    >
      <span aria-hidden className="text-5xl">
        🌱
      </span>
      {showsText(mode) ? (
        <>
          <p className="text-xl font-black">{title}</p>
          <p className="font-bold text-ink/70">Coming soon. Let us pick another one for now.</p>
        </>
      ) : (
        <p className="sr-only">{title} is coming soon.</p>
      )}
    </div>
  );
}
