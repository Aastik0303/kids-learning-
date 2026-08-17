"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loadActiveChild } from "@/services/child";
import { getChild, getToken } from "@/services/session";

/**
 * The landing step after login. The session holds only a token, so the child
 * profile has to be fetched back from the server here — without this step every
 * later screen reads a null child and says "let us set up a profile first",
 * even for a parent whose child already exists.
 */
export default function SelectChildPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    loadActiveChild(token)
      .then((child) => router.replace(child ? "/" : "/onboarding"))
      .catch((err: unknown) => {
        // A child may already be in this session from an earlier load; only
        // block when there is genuinely nothing to go on.
        if (getChild()) {
          router.replace("/");
          return;
        }
        setError(err instanceof Error ? err.message : "We could not load your child profile.");
      });
  }, [router]);

  return (
    <main className="grid min-h-screen place-items-center px-4 font-black">
      {error ? (
        <div className="grid max-w-md gap-4 rounded-[2rem] bg-white p-6 text-center shadow-soft">
          <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p>
          <Link className="rounded-3xl bg-leaf px-5 py-4 text-xl font-black text-white shadow-soft" href="/child/select">
            Try again
          </Link>
          <Link className="font-bold text-leaf" href="/onboarding">
            Set up a child profile
          </Link>
        </div>
      ) : (
        "Loading..."
      )}
    </main>
  );
}
