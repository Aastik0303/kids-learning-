"use client";

import type { VoiceProvider } from "@/services/speech";

export function AvatarControls({
  muted,
  isSpeaking,
  assistantOpen,
  voiceProvider,
  onReplay,
  onStop,
  onMute,
  onAsk,
  onVoiceProviderChange
}: {
  muted: boolean;
  isSpeaking: boolean;
  assistantOpen: boolean;
  voiceProvider: VoiceProvider;
  onReplay: () => void;
  onStop: () => void;
  onMute: () => void;
  onAsk: () => void;
  onVoiceProviderChange: () => void;
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
      <button
        type="button"
        className="avatar-control avatar-control-wide pressable"
        onClick={onVoiceProviderChange}
        aria-label={voiceProvider === "elevenlabs" ? "Switch to free normal browser voice" : "Switch to ElevenLabs voice"}
        title={voiceProvider === "elevenlabs" ? "ElevenLabs voice may use paid credits" : "Normal browser voice is free"}
      >
        {voiceProvider === "elevenlabs" ? "Voice: ElevenLabs" : "Voice: Normal"}
      </button>
    </div>
  );
}
