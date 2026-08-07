"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createChild } from "@/services/child";
import { getToken, saveChild } from "@/services/session";
import { LargeButton } from "@/components/shared/LargeButton";

export default function OnboardingPage() {
  const router = useRouter();
  const [name, setName] = useState("Aaru");
  const [ageGroup, setAgeGroup] = useState("4-5");
  const [language, setLanguage] = useState("English");
  const [avatar, setAvatar] = useState("Sun");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }
    try {
      const child = await createChild(token, name, ageGroup, language);
      saveChild(child);
      sessionStorage.setItem("demo_child_avatar", avatar);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Let us try again.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <form onSubmit={submit} className="grid w-full max-w-md gap-4 rounded-[2rem] bg-white p-6 shadow-soft">
        <h1 className="text-3xl font-black">Child profile</h1>
        <input className="rounded-2xl border-2 border-leaf/20 px-4 py-4 font-bold" value={name} onChange={(e) => setName(e.target.value)} />
        <select className="rounded-2xl border-2 border-leaf/20 px-4 py-4 font-bold" value={ageGroup} onChange={(e) => setAgeGroup(e.target.value)}>
          <option>3-4</option>
          <option>4-5</option>
        </select>
        <select className="rounded-2xl border-2 border-leaf/20 px-4 py-4 font-bold" value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option>English</option>
          <option>Hindi</option>
        </select>
        <div className="grid gap-2">
          <p className="font-bold">Avatar</p>
          <div className="grid grid-cols-3 gap-2">
            {["Sun", "Leaf", "Star"].map((item) => (
              <button
                key={item}
                type="button"
                className={`rounded-2xl px-4 py-4 font-black shadow-soft ${avatar === item ? "bg-leaf text-white" : "bg-[#f5f8ef] text-ink"}`}
                onClick={() => setAvatar(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
        {error ? <p className="rounded-2xl bg-berry/10 p-4 font-bold text-berry">{error}</p> : null}
        <LargeButton tone="leaf">Start</LargeButton>
      </form>
    </main>
  );
}
