"use client";

import { usePathname } from "next/navigation";
import { AIAvatar } from "./AIAvatar";
import { AvatarControls } from "./AvatarControls";
import { AvatarMessage } from "./AvatarMessage";
import { useAvatar } from "./AvatarProvider";

const hiddenRoutes = ["/login", "/signup", "/register", "/onboarding", "/parent"];

export function AvatarDock() {
  const pathname = usePathname();
  const { state, message, effect, isSpeaking, muted, speakMessage, stopSpeaking, toggleMute } = useAvatar();
  const hidden = hiddenRoutes.some((route) => pathname === route || pathname.startsWith(`${route}/`));

  if (hidden) return null;

  return (
    <aside className="avatar-dock no-print" aria-label="Learning buddy">
      <div className="avatar-stage">
        <AIAvatar state={state} effect={effect} isSpeaking={isSpeaking} />
      </div>
      <AvatarMessage message={message} />
      <AvatarControls muted={muted} isSpeaking={isSpeaking} onReplay={() => speakMessage()} onStop={stopSpeaking} onMute={toggleMute} />
    </aside>
  );
}
