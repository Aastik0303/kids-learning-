"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { resendCode, verifyCode } from "@/services/auth";
import { saveAuth } from "@/services/session";
import { LargeButton } from "@/components/shared/LargeButton";
import type { AuthResponse, SignInChallenge } from "@/types";

/**
 * The second step of signing in: the code that went to the parent's inbox.
 *
 * The password proved what they know; this proves they still hold the address
 * the account is on. So the screen has to do three things and no more - say
 * where the code went, take six digits, and let them ask for another one -
 * because a parent reaches this holding a phone with a toddler on their lap.
 *
 * `inputMode="numeric"` and `autoComplete="one-time-code"` are what make it
 * bearable on a phone: the numeric keypad comes up, and iOS and Android both
 * offer the code straight from the notification so it is one tap rather than
 * six.
 *
 * The cooldown is the server's; the countdown here only mirrors it, so pressing
 * early is refused by the thing that actually knows.
 */
export function OtpForm({
  challenge,
  onSignedIn,
  onStartOver
}: {
  challenge: SignInChallenge;
  onSignedIn: (auth: AuthResponse) => void;
  onStartOver: () => void;
}) {
  const [code, setCode] = useState(challenge.dev_code ?? "");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [waitFor, setWaitFor] = useState(challenge.resend_after);
  const box = useRef<HTMLInputElement | null>(null);

  // The code box is the only thing on this screen; there is nothing else the
  // parent could have come here to do.
  useEffect(() => {
    box.current?.focus();
  }, []);

  useEffect(() => {
    if (waitFor <= 0) return;
    const timer = globalThis.setInterval(() => setWaitFor((left) => Math.max(0, left - 1)), 1000);
    return () => globalThis.clearInterval(timer);
  }, [waitFor]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNote("");
    setBusy(true);
    try {
      const auth = await verifyCode(challenge.challenge_id, code);
      saveAuth(auth);
      onSignedIn(auth);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That code did not work. Please try again.");
      setCode("");
      box.current?.focus();
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setError("");
    setNote("");
    try {
      const again = await resendCode(challenge.challenge_id);
      setNote(again.message);
      setWaitFor(again.resend_after);
      if (again.dev_code) setCode(again.dev_code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not send another code.");
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto grid w-full max-w-md gap-4 rounded-[2rem] bg-white p-6 shadow-soft">
      <h1 className="text-3xl font-black text-ink">Check your email</h1>
      <p className="font-bold text-ink/60">
        We sent a code to <span className="text-ink">{challenge.email_hint}</span>. It works for the
        next {Math.round(challenge.expires_in / 60)} minutes.
      </p>

      <label className="grid gap-2 font-bold">
        Your code
        <input
          ref={box}
          className="rounded-2xl border-2 border-leaf/20 px-4 py-4 text-center text-3xl font-black tracking-[0.4em]"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          // The numeric keypad, and the code offered straight from the
          // notification on both phone platforms.
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]*"
          maxLength={6}
          required
          aria-label="The six-digit code we emailed you"
        />
      </label>

      {challenge.dev_code ? (
        <p className="rounded-2xl bg-sunshine/20 p-3 text-sm font-bold text-ink/70">
          No mail server is configured on this machine, so the code is filled in for you. This
          never happens in production.
        </p>
      ) : null}

      {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}
      {note ? <p className="rounded-2xl bg-leaf/10 p-4 font-bold text-leaf">{note}</p> : null}

      <LargeButton tone="leaf" disabled={busy || code.length < 4}>
        {busy ? "Checking…" : "Sign in"}
      </LargeButton>

      <div className="flex items-center justify-between text-sm font-bold">
        <button
          type="button"
          onClick={onResend}
          disabled={waitFor > 0}
          className={waitFor > 0 ? "text-ink/30" : "text-leaf"}
        >
          {waitFor > 0 ? `Send it again in ${waitFor}s` : "Send it again"}
        </button>
        <button type="button" onClick={onStartOver} className="text-ink/50">
          Use a different account
        </button>
      </div>
    </form>
  );
}
