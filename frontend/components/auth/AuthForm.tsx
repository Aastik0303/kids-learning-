"use client";

import { FormEvent, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { login, register } from "@/services/auth";
import { saveAuth } from "@/services/session";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { OtpForm } from "@/components/auth/OtpForm";
import { LargeButton } from "@/components/shared/LargeButton";
import { isSignInChallenge, type AuthResponse, type SignInChallenge } from "@/types";

/**
 * The parent's sign-in and sign-up form.
 *
 * Two ways in, and they end in the same place: Google, drawn by Google and
 * verified on the server, and an email address with a password. The fields
 * start empty - they are a real account holding a real child's name, birth
 * month and whole learning history.
 *
 * The password path has a second step. A right password does not sign anybody
 * in on its own: the server emails a code and answers with a challenge, and
 * `OtpForm` takes it from there. Google skips that - Google has already proved
 * the address, so a code on top would be friction for nothing.
 *
 * Where the parent lands afterwards is the server's answer rather than which
 * form they used: a brand-new account goes to setting a child up, and one that
 * already exists goes to choosing the child. That matters most on the Google
 * button, which is one control for both.
 */
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const isRegister = mode === "register";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Set when the server asked for the emailed code. While it is here, this
  // component shows the code step instead of the form.
  const [challenge, setChallenge] = useState<SignInChallenge | null>(null);

  const goOnwards = useCallback(
    (auth: AuthResponse) => {
      router.push(auth.is_new_account ? "/onboarding" : "/child/select");
    },
    [router]
  );

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (isRegister && password !== confirmPassword) {
      setError("Those two passwords are not the same.");
      return;
    }
    setBusy(true);
    try {
      if (isRegister) {
        const auth = await register(name, email, password);
        saveAuth(auth);
        goOnwards(auth);
        return;
      }

      const result = await login(email, password);
      if (isSignInChallenge(result)) {
        // No session yet, and nothing in `result` is one. The code step is
        // what mints it.
        setChallenge(result);
        return;
      }
      saveAuth(result);
      goOnwards(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Let us try again.");
    } finally {
      setBusy(false);
    }
  }

  if (challenge) {
    return (
      <OtpForm
        challenge={challenge}
        onSignedIn={goOnwards}
        onStartOver={() => {
          setChallenge(null);
          setPassword("");
          setError("");
        }}
      />
    );
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto grid w-full max-w-md gap-4 rounded-[2rem] bg-white p-6 shadow-soft">
      <h1 className="text-3xl font-black text-ink">{isRegister ? "Create your account" : "Welcome back"}</h1>

      <GoogleSignInButton onSignedIn={goOnwards} onError={setError} />

      {isRegister ? (
        <label className="grid gap-2 font-bold">
          Your name
          <input
            className="rounded-2xl border-2 border-leaf/20 px-4 py-4"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
            required
          />
        </label>
      ) : null}
      <label className="grid gap-2 font-bold">
        Email
        <input
          className="rounded-2xl border-2 border-leaf/20 px-4 py-4"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
      </label>
      <label className="grid gap-2 font-bold">
        Password
        <input
          className="rounded-2xl border-2 border-leaf/20 px-4 py-4"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          // Eight, matching the server, so a rejected password is caught here
          // rather than coming back as an error the parent cannot act on.
          minLength={isRegister ? 8 : undefined}
          autoComplete={isRegister ? "new-password" : "current-password"}
          required
        />
        {isRegister ? <span className="text-sm font-medium text-ink/50">At least 8 characters.</span> : null}
      </label>
      {isRegister ? (
        <label className="grid gap-2 font-bold">
          Confirm password
          <input
            className="rounded-2xl border-2 border-leaf/20 px-4 py-4"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>
      ) : null}
      {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}
      <LargeButton tone="leaf" disabled={busy}>
        {isRegister ? "Create account" : "Sign in"}
      </LargeButton>
    </form>
  );
}
