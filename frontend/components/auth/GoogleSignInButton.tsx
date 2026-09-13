"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { googleConfig, signInWithGoogle } from "@/services/auth";
import { saveAuth } from "@/services/session";
import type { AuthResponse } from "@/types";

/**
 * "Continue with Google", drawn by Google.
 *
 * The button itself is rendered by Google Identity Services rather than by this
 * app. That is not laziness: Google's branding rules cover the mark, the
 * wording and the spacing, and a hand-drawn lookalike is both against those
 * rules and the shape a phishing page takes. The script is loaded from
 * accounts.google.com and nothing else.
 *
 * What comes back from it is a **credential** - an ID token signed by Google -
 * and this component does not read it. It is posted straight to `/auth/google`,
 * where the signature is checked against Google's published keys and the
 * audience against this app's own client id. Until that happens it is just a
 * string a browser handed us.
 *
 * The button appears only where the server said it can verify one: `enabled`
 * comes from `/auth/google/config`, so a deployment with no `GOOGLE_CLIENT_ID`
 * shows the email form alone rather than a button that fails on tap.
 *
 * Deliberately not One Tap. The automatic prompt appears over the page without
 * being asked for, and the one screen a parent of a small child is trying to
 * get through quickly is this one.
 */

type GoogleCredentialResponse = { credential?: string };

type GoogleIdentityServices = {
  accounts: {
    id: {
      initialize(options: {
        client_id: string;
        callback(response: GoogleCredentialResponse): void;
        auto_select?: boolean;
        cancel_on_tap_outside?: boolean;
        use_fedcm_for_prompt?: boolean;
      }): void;
      renderButton(
        parent: HTMLElement,
        options: {
          type?: "standard" | "icon";
          theme?: "outline" | "filled_blue" | "filled_black";
          size?: "small" | "medium" | "large";
          text?: "signin_with" | "signup_with" | "continue_with";
          shape?: "rectangular" | "pill";
          logo_alignment?: "left" | "center";
          width?: number;
        }
      ): void;
      disableAutoSelect(): void;
    };
  };
};

declare global {
  interface Window {
    google?: GoogleIdentityServices;
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";

/** One script tag for the page, however many buttons ask for it. */
function loadGoogleScript(): Promise<GoogleIdentityServices> {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("no window"));
      return;
    }
    if (window.google?.accounts?.id) {
      resolve(window.google);
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    const script = existing ?? document.createElement("script");
    const onReady = () => {
      if (window.google?.accounts?.id) resolve(window.google);
      else reject(new Error("Google sign-in did not load."));
    };

    script.addEventListener("load", onReady, { once: true });
    script.addEventListener("error", () => reject(new Error("Google sign-in did not load.")), {
      once: true
    });

    if (!existing) {
      script.src = GSI_SRC;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  });
}

export function GoogleSignInButton({
  onSignedIn,
  onError
}: {
  /** Called once the app's own session has been saved. */
  onSignedIn: (auth: AuthResponse) => void;
  onError?: (message: string) => void;
}) {
  const target = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);

  // Kept in a ref so the effect below does not re-run - and re-render Google's
  // button - every time the page it sits on renders for some other reason.
  const handlers = useRef({ onSignedIn, onError });
  handlers.current = { onSignedIn, onError };

  const onCredential = useCallback(async (response: GoogleCredentialResponse) => {
    const credential = response?.credential;
    if (!credential) {
      handlers.current.onError?.("Google sign-in was cancelled. Please try again.");
      return;
    }
    setBusy(true);
    try {
      const auth = await signInWithGoogle(credential);
      saveAuth(auth);
      handlers.current.onSignedIn(auth);
    } catch (error) {
      handlers.current.onError?.(
        error instanceof Error ? error.message : "We could not finish that Google sign-in."
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const config = await googleConfig();
      if (cancelled || !config.enabled || !config.client_id) return;

      let gsi: GoogleIdentityServices;
      try {
        gsi = await loadGoogleScript();
      } catch {
        // A blocked script or an offline browser. The email form beside this is
        // a complete way in, so this stays silent rather than putting an error
        // in front of a parent about a button they never pressed.
        return;
      }
      if (cancelled || !target.current) return;

      gsi.accounts.id.initialize({
        client_id: config.client_id,
        callback: onCredential,
        // No silent re-sign-in: signing out has to stay signed out.
        auto_select: false,
        use_fedcm_for_prompt: true
      });
      target.current.innerHTML = "";
      gsi.accounts.id.renderButton(target.current, {
        type: "standard",
        theme: "outline",
        size: "large",
        text: "continue_with",
        shape: "pill",
        logo_alignment: "left",
        // Google wants a number, and its own maximum is 400.
        width: Math.min(400, Math.max(200, Math.round(target.current.clientWidth || 320)))
      });
      setReady(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [onCredential]);

  return (
    <div
      className="grid gap-3"
      // Nothing is announced while the server is being asked whether Google is
      // configured at all: an empty region that may stay empty is not news.
      aria-live="polite"
    >
      <div ref={target} className="flex min-h-0 justify-center [&>div]:!w-full" />
      {ready && busy ? (
        <p className="text-center text-sm font-bold text-ink/60">Signing you in…</p>
      ) : null}
      {ready ? (
        <div className="flex items-center gap-3 text-sm font-bold text-ink/40">
          <span className="h-px flex-1 bg-ink/10" />
          or
          <span className="h-px flex-1 bg-ink/10" />
        </div>
      ) : null}
    </div>
  );
}
