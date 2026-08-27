"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { forgotPassword, resetPassword } from "@/services/auth";
import { LargeButton } from "@/components/shared/LargeButton";

/**
 * Resetting a parent's password.
 *
 * The two endpoints behind this have existed since auth stopped being a mock,
 * and nothing in the app ever called them: a parent who forgot their password
 * had no way back in. There is no mailer yet, so in development the server
 * returns the token and this page fills it in; in production it does not, and
 * the parent pastes the one they were sent.
 */
export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [asked, setAsked] = useState(false);

  async function ask(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const answer = await forgotPassword(email);
      setNotice(answer.message);
      setAsked(true);
      // Development only: the server says so by sending one at all.
      if (answer.reset_token) setToken(answer.reset_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not start that reset.");
    }
  }

  async function apply(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const answer = await resetPassword(token, password);
      setNotice(answer.message);
      router.push("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "That reset link is no longer valid.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <div className="grid w-full max-w-md gap-4">
        <form onSubmit={asked ? apply : ask} className="grid gap-4 rounded-[2rem] bg-white p-6 shadow-soft">
          <h1 className="text-3xl font-black text-ink">Reset your password</h1>

          <label className="grid gap-2 font-bold">
            Parent email
            <input
              className="rounded-2xl border-2 border-leaf/20 px-4 py-4"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              disabled={asked}
            />
          </label>

          {asked ? (
            <>
              <label className="grid gap-2 font-bold">
                Reset code
                <input
                  className="rounded-2xl border-2 border-leaf/20 px-4 py-4"
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                />
              </label>
              <label className="grid gap-2 font-bold">
                New password
                <input
                  className="rounded-2xl border-2 border-leaf/20 px-4 py-4"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
            </>
          ) : null}

          {notice ? <p className="rounded-2xl bg-leaf/10 p-4 font-bold text-leaf">{notice}</p> : null}
          {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}

          <LargeButton tone="leaf">{asked ? "Set new password" : "Send reset code"}</LargeButton>
        </form>

        <Link className="text-center font-bold text-leaf" href="/login">
          Back to login
        </Link>
      </div>
    </main>
  );
}
