"use client";

export function AvatarControls({
  muted,
  isSpeaking,
  onReplay,
  onStop,
  onMute
}: {
  muted: boolean;
  isSpeaking: boolean;
  onReplay: () => void;
  onStop: () => void;
  onMute: () => void;
}) {
  return (
    <div className="avatar-controls" aria-label="Avatar controls">
      <button type="button" className="avatar-control pressable" onClick={onReplay} aria-label="Read avatar message">
        🔊
      </button>
      <button type="button" className="avatar-control pressable" onClick={onStop} disabled={!isSpeaking} aria-label="Stop avatar voice">
        ⏹️
      </button>
      <button type="button" className="avatar-control pressable" onClick={onMute} aria-label={muted ? "Unmute avatar voice" : "Mute avatar voice"}>
        {muted ? "🔇" : "🎤"}
      </button>
    </div>
  );
}
