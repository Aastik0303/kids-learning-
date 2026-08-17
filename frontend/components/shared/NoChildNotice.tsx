import Link from "next/link";

/**
 * Shown when a screen needs a child and there is not one yet. Always offers the
 * way out, so the message is never a dead end.
 */
export function NoChildNotice({ status, error }: { status: string; error?: string }) {
  if (status === "signed-out") {
    return (
      <div className="grid max-w-md gap-3 rounded-[2rem] bg-white p-6 shadow-soft">
        <p className="text-xl font-black">Please log in first</p>
        <Link className="rounded-3xl bg-leaf px-5 py-4 text-center text-xl font-black text-white shadow-soft" href="/login">
          Parent Login
        </Link>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="grid max-w-md gap-3 rounded-[2rem] bg-white p-6 shadow-soft">
        <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p>
        <Link className="rounded-3xl bg-white px-5 py-4 text-center text-xl font-black text-ink shadow-soft" href="/">
          Back Home
        </Link>
      </div>
    );
  }

  return (
    <div className="grid max-w-md gap-3 rounded-[2rem] bg-white p-6 shadow-soft">
      <p className="text-xl font-black">No child profile yet</p>
      <p className="font-bold text-ink/70">Add a child to start learning.</p>
      <Link className="rounded-3xl bg-leaf px-5 py-4 text-center text-xl font-black text-white shadow-soft" href="/onboarding">
        Add a child
      </Link>
    </div>
  );
}
