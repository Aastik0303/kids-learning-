"use client";

import { useEffect, useMemo, useState } from "react";
import { AIAvatar } from "@/components/avatar/AIAvatar";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { useSpeechRecognition, useTextToSpeech } from "@/services/toddlerVoice";
import { answerToddlerLesson, startToddlerLesson } from "@/services/toddler";
import { getChild, saveChild } from "@/services/session";
import type { ChildProfile, ToddlerActivity, ToddlerModule, ToddlerResponse } from "@/types";

function activityNeedsVoice(activity: ToddlerActivity | null) {
  return activity?.type === "repeat_after_me";
}

export function ToddlerLesson({
  child,
  module,
  onHome,
  onChildChange
}: {
  child: ChildProfile;
  module: ToddlerModule;
  onHome: () => void;
  onChildChange: (child: ChildProfile) => void;
}) {
  const [lesson, setLesson] = useState<ToddlerResponse | null>(null);
  const [busy, setBusy] = useState(true);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState("");
  const { state, effect, isSpeaking, setAvatar } = useAvatar();
  const tts = useTextToSpeech();
  const stt = useSpeechRecognition();

  const activity = lesson?.activity ?? null;
  const canTapChoices = Boolean(activity?.choices.length);

  useEffect(() => {
    let active = true;
    setBusy(true);
    startToddlerLesson(child.child_id, module, 1).then((response) => {
      if (!active) return;
      setLesson(response);
      setAvatar(response.avatar);
      setBusy(false);
    }).catch((err) => {
      if (!active) return;
      setError(err instanceof Error ? err.message : "Let's try again.");
      setBusy(false);
    });
    return () => {
      active = false;
    };
  }, [child.child_id, module, setAvatar]);

  useEffect(() => {
    if (!activity || !lesson) return;
    const currentActivity = activity;
    let cancelled = false;
    async function guideActivity() {
      setTranscript("");
      setError("");
      setAvatar({ state: "speaking", message: currentActivity.speech, animationEffect: "story_transition", durationMs: null });
      await tts.speak(currentActivity.speech);
      if (cancelled) return;
      if (currentActivity.type === "introduce") {
        window.setTimeout(() => {
          if (!cancelled) submitAnswer(currentActivity.answer ?? currentActivity.concept, currentActivity.answer ?? currentActivity.concept);
        }, 500);
        return;
      }
      setAvatar({
        state: activityNeedsVoice(currentActivity) ? "listening" : "happy",
        message: activityNeedsVoice(currentActivity) ? "Tap the microphone." : "Tap one big answer.",
        animationEffect: "none",
        durationMs: null
      });
    }
    guideActivity();
    return () => {
      cancelled = true;
    };
  }, [activity?.activity_id]);

  async function restart(practice = false) {
    setBusy(true);
    try {
      const response = await startToddlerLesson(child.child_id, module, 1, practice);
      setLesson(response);
      setAvatar(response.avatar);
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(answer: string, recognized = answer) {
    if (!lesson || busy) return;
    setBusy(true);
    setError("");
    setAvatar({ state: "thinking", message: "Let me listen...", animationEffect: "none", durationMs: null });
    try {
      const response = await answerToddlerLesson(lesson.session_id, answer, recognized);
      setLesson(response);
      setAvatar(response.avatar);
      const stored = getChild();
      if (stored) {
        const updated = { ...stored, stars: response.total_stars };
        saveChild(updated);
        onChildChange(updated);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Oops! Try again.";
      setError(message);
      setAvatar({ state: "encouraging", message, speak: true, animationEffect: "gentle_hint" });
    } finally {
      setBusy(false);
    }
  }

  async function listen() {
    if (!activity || !lesson || busy) return;
    setAvatar({ state: "listening", message: "I'm listening...", animationEffect: "none", durationMs: null });
    const result = await stt.startListening(lesson.session_id, activity);
    if (!result || !result.transcript.trim()) {
      const message = stt.error || "Oops! I couldn't hear you 😊 Try again!";
      setError(message);
      setAvatar({ state: "encouraging", message, speak: true, animationEffect: "gentle_hint" });
      return;
    }
    setTranscript(result.transcript);
    await submitAnswer(result.transcript, result.transcript);
  }

  const feedback = useMemo(() => {
    if (!lesson?.evaluation) return "";
    if (lesson.evaluation.result === "correct" || lesson.evaluation.result === "close") return "🎉 ⭐ 👏";
    return "😊 💛";
  }, [lesson?.evaluation]);

  if (lesson?.level_completed) {
    return (
      <section className="grid min-h-[calc(100vh-3rem)] content-center gap-5 text-center">
        <div className="surface-panel mx-auto grid w-full max-w-2xl gap-5 rounded-[2rem] p-7">
          <div className="mx-auto h-32 w-32">
            <AIAvatar state="celebrating" effect="confetti" isSpeaking={isSpeaking} />
          </div>
          <h1 className="text-5xl font-black text-ink">YOU DID IT!</h1>
          <p className="text-6xl">🎉🌟🎉</p>
          <p className="text-4xl font-black text-ink">⭐⭐⭐</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <button className="pressable rounded-3xl bg-leaf px-6 py-5 text-2xl font-black text-white shadow-soft" onClick={() => restart(false)}>
              ▶️ Keep Learning
            </button>
            <button className="pressable rounded-3xl bg-sunshine px-6 py-5 text-2xl font-black text-ink shadow-soft" onClick={() => restart(true)}>
              🎮 Practice
            </button>
          </div>
          <button className="pressable rounded-3xl bg-white px-6 py-4 text-xl font-black text-ink shadow-soft" onClick={onHome}>
            Home
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="grid gap-5">
      <div className="surface-panel flex flex-wrap items-center justify-between gap-4 rounded-[2rem] p-4">
        <button className="pressable rounded-full bg-white px-5 py-4 text-xl font-black text-ink shadow-soft" onClick={onHome}>Home</button>
        <span className="rounded-full bg-sunshine px-5 py-4 text-2xl font-black text-ink shadow-soft">⭐ {child.stars}</span>
      </div>

      <div data-guide-id="toddler-activity" className="surface-panel grid gap-5 rounded-[2rem] p-5 text-center">
        <div className="mx-auto grid w-full max-w-xl justify-items-center gap-4 rounded-[2rem] bg-[#f7fbff] p-5">
          <div className="h-36 w-36">
            <AIAvatar state={state} effect={effect} isSpeaking={isSpeaking || tts.speaking} />
          </div>
          <p className="rounded-[2rem] bg-white px-5 py-4 text-3xl font-black text-ink shadow-soft">{lesson?.guide.speech ?? "Hi!"}</p>
        </div>

        {activity ? (
          <div className="grid justify-items-center gap-5">
            <h1 className="text-6xl font-black text-ink sm:text-7xl">{activity.concept}</h1>
            <p className="text-8xl" aria-hidden="true">{activity.emoji}</p>
            {activity.word ? <p className="text-4xl font-black text-leaf">{activity.word}</p> : null}
            {activity.visual_items.length ? (
              <div className="flex flex-wrap justify-center gap-4">
                {activity.visual_items.map((item, index) => (
                  <span key={`${item}-${index}`} className="grid h-24 w-24 place-items-center rounded-[2rem] bg-white text-5xl font-black shadow-soft">{item}</span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {activityNeedsVoice(activity) ? (
          <div data-guide-id="toddler-microphone" className="grid justify-items-center gap-3 rounded-[2rem] bg-sunshine/20 p-5">
            <button
              type="button"
              disabled={busy || tts.speaking || stt.listening}
              onClick={listen}
              className={`pressable grid h-36 w-36 place-items-center rounded-full text-4xl font-black shadow-soft ${stt.listening ? "bg-sky text-white" : "bg-leaf text-white"} disabled:opacity-60`}
              aria-label="Speak"
            >
              🎤
            </button>
            <p className="text-2xl font-black text-ink">{stt.listening ? "Listening..." : "Your turn!"}</p>
            {transcript ? <p className="rounded-full bg-white px-4 py-3 text-xl font-black text-ink shadow-soft">{transcript}</p> : null}
          </div>
        ) : null}

        {canTapChoices && activity ? (
          <div data-guide-id="toddler-choices" className="grid gap-3 sm:grid-cols-3">
            {activity.choices.map((choice) => (
              <button
                key={choice}
                type="button"
                disabled={busy || tts.speaking}
                onClick={() => submitAnswer(choice)}
                className="pressable min-h-36 rounded-[2rem] bg-white p-5 text-6xl font-black text-ink shadow-soft disabled:opacity-60"
              >
                {choice}
              </button>
            ))}
          </div>
        ) : null}

        {feedback ? <p className="text-5xl">{feedback}</p> : null}
        {(error || stt.error) ? <p className="rounded-[2rem] bg-berry/10 p-4 text-xl font-black text-berry">{error || stt.error}</p> : null}
      </div>
    </section>
  );
}
