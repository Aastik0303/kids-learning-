"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getChild } from "@/services/session";

export default function SelectChildPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(getChild() ? "/" : "/onboarding");
  }, [router]);
  return <main className="grid min-h-screen place-items-center font-black">Loading...</main>;
}
