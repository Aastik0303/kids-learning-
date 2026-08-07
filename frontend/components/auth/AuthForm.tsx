"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login, register } from "@/services/auth";
import { saveAuth } from "@/services/session";
import { LargeButton } from "@/components/shared/LargeButton";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [name, setName] = useState("Test Parent");
  const [email, setEmail] = useState("parent@example.com");
  const [password, setPassword] = useState("demo1234");
  const [confirmPassword, setConfirmPassword] = useState("demo1234");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (mode === "register" && password !== confirmPassword) {
      setError("Passwords need to match before we create the demo account.");
      return;
    }
    try {
      const auth = mode === "register" ? await register(name, email, password) : await login(email, password);
      saveAuth(auth);
      router.push(mode === "register" ? "/onboarding" : "/child/select");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Let us try again.");
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto grid w-full max-w-md gap-4 rounded-[2rem] bg-white p-6 shadow-soft">
      <h1 className="text-3xl font-black text-ink">{mode === "register" ? "Create demo account" : "Welcome back"}</h1>
      {mode === "register" ? (
        <label className="grid gap-2 font-bold">
          Parent name
          <input className="rounded-2xl border-2 border-leaf/20 px-4 py-4" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
      ) : null}
      <label className="grid gap-2 font-bold">
        Demo email
        <input className="rounded-2xl border-2 border-leaf/20 px-4 py-4" value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label className="grid gap-2 font-bold">
        Demo password
        <input className="rounded-2xl border-2 border-leaf/20 px-4 py-4" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
      {mode === "register" ? (
        <label className="grid gap-2 font-bold">
          Confirm password
          <input className="rounded-2xl border-2 border-leaf/20 px-4 py-4" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
        </label>
      ) : null}
      {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}
      <LargeButton tone="leaf">{mode === "register" ? "Register" : "Login"}</LargeButton>
    </form>
  );
}
