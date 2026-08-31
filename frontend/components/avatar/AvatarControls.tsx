"use client";

export function AvatarControls({
  muted,
  isSpeaking,
  assistantOpen,
  onReplay,
  onStop,
  onMute,
  onAsk
}: {
  muted: boolean;
  isSpeaking: boolean;
  assistantOpen: boolean;
  onReplay: () => void;
  onStop: () => void;
  onMute: () => void;
  onAsk: () => void;
}) {
  return (
    <div className="avatar-controls" aria-label="Avatar controls">
      <button type="button" className="avatar-control avatar-control-wide pressable" onClick={onAsk} aria-expanded={assistantOpen} aria-label="Ask the AI guide">
        {assistantOpen ? "Close" : "Ask"}
      </button>
      <button type="button" className="avatar-control avatar-control-wide pressable" onClick={onReplay} aria-label="Read avatar message">
        Play
      </button>
      {isSpeaking ? (
        <button type="button" className="avatar-control avatar-control-wide pressable" onClick={onStop} aria-label="Stop avatar voice">
          Stop
        </button>
      ) : null}
      <button type="button" className="avatar-control avatar-control-wide pressable" onClick={onMute} aria-label={muted ? "Unmute avatar voice" : "Mute avatar voice"}>
        {muted ? "Unmute" : "Mute"}
      </button>
    </div>
  );
}
