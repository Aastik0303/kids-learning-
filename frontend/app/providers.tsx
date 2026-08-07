"use client";

import { AvatarProvider } from "@/components/avatar/AvatarProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return <AvatarProvider>{children}</AvatarProvider>;
}
