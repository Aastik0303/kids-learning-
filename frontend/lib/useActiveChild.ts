"use client";

import { useCallback, useEffect, useState } from "react";
import { loadActiveChild } from "@/services/child";
import { getChild, getToken } from "@/services/session";
import type { ChildProfile } from "@/types";

export type ActiveChild = {
  child: ChildProfile | null;
  /** "loading" until we know; "none" means signed in with no child yet. */
  status: "loading" | "ready" | "none" | "signed-out" | "error";
  error: string;
};

/**
 * The child every child-facing screen works from.
 *
 * The session stores a token, not a profile, so on a fresh load the child has
 * to come back from the server. Screens that read `getChild()` directly showed
 * "let us set up a profile first" to parents whose child already existed,
 * simply because nothing had fetched it yet.
 *
 * The stored copy is shown at once and then re-read from the server, never
 * trusted on its own. Progress is a snapshot of a curriculum that can gain a
 * subject at any time — Nursery gained Hindi — and the server opens the new
 * subject's first topic on read. A browser holding the profile it saved before
 * that showed the whole subject locked with no way in, because the copy on the
 * screen simply predated it.
 */
export function useActiveChild(): ActiveChild & { refresh: () => void } {
  const [state, setState] = useState<ActiveChild>({ child: null, status: "loading", error: "" });

  const sync = useCallback(() => {
    const stored = getChild();
    if (stored) {
      setState({ child: stored, status: "ready", error: "" });
    }
    const token = getToken();
    if (!token) {
      if (!stored) setState({ child: null, status: "signed-out", error: "" });
      return;
    }
    loadActiveChild(token)
      .then((child) => {
        // A stored child with nothing to refresh it from is still better than
        // an empty screen, so only an empty cache falls back to "none".
        if (child || !stored) {
          setState({ child, status: child ? "ready" : "none", error: "" });
        }
      })
      .catch((err: unknown) => {
        if (stored) return;
        setState({
          child: null,
          status: "error",
          error: err instanceof Error ? err.message : "We could not load your child profile."
        });
      });
  }, []);

  useEffect(() => {
    sync();
    window.addEventListener("little-learning-session", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("little-learning-session", sync);
      window.removeEventListener("storage", sync);
    };
  }, [sync]);

  return { ...state, refresh: sync };
}
