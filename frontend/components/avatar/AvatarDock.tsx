"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { askGuideQuestion } from "@/services/guide";
import { captureSpeechTranscript } from "@/services/speech";
import { AIAvatar } from "./AIAvatar";
import { AvatarControls } from "./AvatarControls";
import { AvatarMessage } from "./AvatarMessage";
import { useAvatar } from "./AvatarProvider";

const hiddenRoutes = ["/login", "/signup", "/register", "/onboarding", "/parent", "/word-coach", "/sentence-coach"];

type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
};

export function AvatarDock() {
  const pathname = usePathname();
  const { state, message, effect, isSpeaking, muted, voiceProvider, setAvatar, speakMessage, stopSpeaking, toggleMute, toggleVoiceProvider } = useAvatar();
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const hidden = hiddenRoutes.some((route) => pathname === route || pathname.startsWith(`${route}/`));

  useEffect(() => {
    if (assistantOpen) inputRef.current?.focus();
  }, [assistantOpen]);

  async function ask(nextQuestion: string) {
    const cleanQuestion = nextQuestion.trim();
    if (!cleanQuestion || busy) return;

    const userMessage: ConversationMessage = { role: "user", content: cleanQuestion };
    const nextConversation = [...conversation, userMessage].slice(-8);
    setQuestion("");
    setError("");
    setBusy(true);
    setConversation(nextConversation);
    setAvatar({ state: "thinking", message: "Let me think about that...", speak: false, animationEffect: "none", durationMs: null });

    try {
      const response = await askGuideQuestion({ question: cleanQuestion, route: pathname, conversation: nextConversation });
      const assistantMessage: ConversationMessage = { role: "assistant", content: response.message };
      setConversation((current) => [...current, assistantMessage].slice(-8));
      setAvatar({ ...response.avatar, message: response.message, speak: true, durationMs: null });
    } catch {
      const fallback = "I could not connect just now. Please ask me again.";
      setError(fallback);
      setAvatar({ state: "encouraging", message: fallback, speak: true, animationEffect: "gentle_hint", durationMs: null });
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  async function startListening() {
    if (busy || listening) return;
    stopSpeaking();
    setError("");
    setListening(true);
    setAvatar({ state: "thinking", message: "I am listening...", speak: false, animationEffect: "pulse", durationMs: null });
    try {
      const transcript = await captureSpeechTranscript();
      setQuestion(transcript);
      await ask(transcript);
    } catch (voiceError) {
      const nextError = voiceError instanceof Error ? voiceError.message : "Voice input did not work. Type your question instead.";
      setError(nextError);
      setAvatar({ state: "encouraging", message: nextError, speak: false, animationEffect: "gentle_hint", durationMs: null });
    } finally {
      setListening(false);
    }
  }

  if (hidden) return null;

  return (
    <aside className={`avatar-dock no-print ${assistantOpen ? "avatar-dock-open" : ""}`} aria-label="AI learning guide">
      {assistantOpen ? (
        <section className="avatar-conversation" aria-label="Conversation with AI guide">
          <div className="avatar-conversation-header">
            <div>
              <strong>Ask your AI guide</strong>
              <span>Numbers, letters, colours, shapes, or app help</span>
            </div>
            <button type="button" className="avatar-chat-close pressable" onClick={() => setAssistantOpen(false)} aria-label="Close AI guide">
              Close
            </button>
          </div>
          {conversation.length ? (
            <div className="avatar-chat-history" aria-live="polite">
              {conversation.map((item, index) => (
                <p key={`${item.role}-${index}`} className={`avatar-chat-message avatar-chat-${item.role}`}>
                  <span>{item.role === "user" ? "You" : "Guide"}</span>
                  {item.content}
                </p>
              ))}
              {busy ? <p className="avatar-chat-status">Guide is thinking...</p> : null}
            </div>
          ) : (
            <p className="avatar-chat-empty">Ask a question by typing or talking.</p>
          )}
          <form className="avatar-chat-form" onSubmit={submit}>
            <input
              ref={inputRef}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What would you like to know?"
              aria-label="Question for AI guide"
              disabled={busy || listening}
            />
            <button type="button" className="avatar-chat-talk pressable" onClick={startListening} disabled={busy || listening}>
              {listening ? "Listening..." : "Talk"}
            </button>
            <button type="submit" className="avatar-chat-send pressable" disabled={busy || listening || !question.trim()}>
              Ask
            </button>
          </form>
          {error ? (
            <p className="avatar-chat-error" role="alert">
              {error}
            </p>
          ) : null}
        </section>
      ) : null}
      <div className="avatar-stage">
        <AIAvatar state={state} effect={effect} isSpeaking={isSpeaking} />
      </div>
      <AvatarMessage message={message} />
      <AvatarControls
        muted={muted}
        isSpeaking={isSpeaking}
        assistantOpen={assistantOpen}
        voiceProvider={voiceProvider}
        onReplay={() => speakMessage()}
        onStop={stopSpeaking}
        onMute={toggleMute}
        onAsk={() => setAssistantOpen((current) => !current)}
        onVoiceProviderChange={toggleVoiceProvider}
      />
    </aside>
  );
}
