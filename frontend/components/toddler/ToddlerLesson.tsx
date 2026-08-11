"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AIAvatar } from "@/components/avatar/AIAvatar";
import { visualGuideClass, type VisualGuideAction } from "@/components/guide/VisualGuideRenderer";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { askGuideQuestion } from "@/services/guide";
import { hasGuideSpeechIntent } from "@/services/speech";
import { useSpeechRecognition, useTextToSpeech } from "@/services/toddlerVoice";
import { answerToddlerLesson, startToddlerLesson } from "@/services/toddler";
import { registerToddlerGuideContext, requestToddlerGuide, toddlerQuestionContext, toddlerStateContext } from "@/services/toddlerGuide";
import { getChild, saveChild } from "@/services/session";
import type { ChildProfile, ToddlerActivity, ToddlerModule, ToddlerResponse } from "@/types";

function activityAcceptsVoice(activity: ToddlerActivity | null) {
  return Boolean(activity && activity.type !== "introduce" && (activity.answer || activity.accepted.length || activity.choices.length));
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
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [visualAction, setVisualAction] = useState<VisualGuideAction>(null);
  const [countGuideEnabled, setCountGuideEnabled] = useState(false);
  const answerInFlightRef = useRef(false);
  const { state, effect, isSpeaking, setAvatar } = useAvatar();
  const tts = useTextToSpeech();
  const stt = useSpeechRecognition();

  const activity = lesson?.activity ?? null;
  const canTapChoices = Boolean(activity?.choices.length);

  function applyGuideVisuals(guide: Awaited<ReturnType<typeof requestToddlerGuide>>, showCountingGuide = false) {
    const safeTargets = new Set(["toddler-activity", "toddler-microphone", "toddler-choices"]);
    if (showCountingGuide) {
      setHighlightId(guide.ui_action.target && safeTargets.has(guide.ui_action.target) ? guide.ui_action.target : null);
      setVisualAction(guide.visual_action);
      setCountGuideEnabled(true);
      return;
    }
    setHighlightId(null);
    setVisualAction(null);
    setCountGuideEnabled(false);
  }

  useEffect(() => {
    let active = true;
    setBusy(true);
    startToddlerLesson(child.child_id, module, 1).then((response) => {
      if (!active) return;
      setLesson(response);
      setAvatar({ ...response.avatar, speak: false });
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
    registerToddlerGuideContext(child, lesson);
    return () => registerToddlerGuideContext(child, null);
  }, [child, lesson]);

  useEffect(() => {
    if (!activity || !lesson) return;
    const currentActivity = activity;
    const currentLesson = lesson;
    let cancelled = false;
    async function guideActivity() {
      setTranscript("");
      setError("");
      let spokenMessage = currentActivity.speech;
      try {
        const guide = await requestToddlerGuide({ child, lesson: currentLesson, event: "LEVEL_QUESTION_LOADED" });
        spokenMessage = guide.message;
        applyGuideVisuals(guide, false);
        setLesson((current) => current?.activity?.activity_id === currentActivity.activity_id
          ? { ...current, guide: { ...current.guide, speech: spokenMessage }, avatar: guide.avatar }
          : current);
        setAvatar({ ...guide.avatar, speak: false, durationMs: null });
      } catch {
        setAvatar({ state: "speaking", message: spokenMessage, speak: false, animationEffect: "story_transition", durationMs: null });
      }
      await tts.speak(spokenMessage);
      if (cancelled) return;
      if (currentActivity.type === "introduce") {
        window.setTimeout(() => {
          if (!cancelled) submitAnswer(currentActivity.answer ?? currentActivity.concept, currentActivity.answer ?? currentActivity.concept);
        }, 500);
        return;
      }
      setAvatar({
        state: activityAcceptsVoice(currentActivity) ? "listening" : "happy",
        message: currentActivity.choices.length ? "Tap the microphone or one big answer." : "Tap the microphone and tell me.",
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
      setAvatar({ ...response.avatar, speak: false });
      setHighlightId(null);
      setVisualAction(null);
      setCountGuideEnabled(false);
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(answer: string, recognized = answer) {
    if (!lesson || busy || answerInFlightRef.current) return;
    answerInFlightRef.current = true;
    setBusy(true);
    setError("");
    setAvatar({ state: "thinking", message: "Let me listen...", animationEffect: "none", durationMs: null });
    try {
      const response = await answerToddlerLesson(lesson.session_id, answer, recognized);
      if (response.evaluation?.retry && !response.question_changed && response.activity) {
        const guide = await requestToddlerGuide({ child, lesson: response, event: "LEVEL_ANSWER_INCORRECT", recognizedSpeech: recognized });
        applyGuideVisuals(guide, response.attempt_count >= 2);
        const guidedResponse = { ...response, guide: { ...response.guide, speech: guide.message }, avatar: guide.avatar };
        setLesson(guidedResponse);
        setAvatar({ ...guide.avatar, speak: false, durationMs: null });
        await tts.speak(guide.message);
      } else {
        setLesson(response);
        setAvatar({ ...response.avatar, speak: false });
        setHighlightId(null);
        setVisualAction(null);
        setCountGuideEnabled(false);
      }
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
      answerInFlightRef.current = false;
      setBusy(false);
    }
  }

  async function askToddlerGuide(question: string, forceCountingGuide = false) {
    if (!lesson || !activity) return;
    setBusy(true);
    setError("");
    setAvatar({ state: "thinking", message: "Let me help...", speak: false, animationEffect: "pulse", durationMs: null });
    try {
      const guide = await askGuideQuestion({
        question,
        route: "/toddler",
        sessionId: lesson.session_id,
        screen: "toddler_lesson",
        questionContext: toddlerQuestionContext(activity, module, lesson.attempt_count, question),
        toddlerContext: toddlerStateContext(child, lesson, question),
        learningMode: "toddler",
        topic: module,
        attempt: lesson.attempt_count
      });
      applyGuideVisuals(guide, forceCountingGuide || lesson.attempt_count >= 2);
      setLesson((current) => current ? { ...current, guide: { ...current.guide, speech: guide.message }, avatar: guide.avatar } : current);
      setAvatar({ ...guide.avatar, speak: false, durationMs: null });
      await tts.speak(guide.message);
    } finally {
      setBusy(false);
    }
  }

  async function listen() {
    if (!activity || !lesson || busy) return;
    setTranscript("");
    setError("");
    stt.clearError();
    tts.stop();
    setAvatar({ state: "listening", message: "I'm listening...", animationEffect: "none", durationMs: null });
    await new Promise((resolve) => window.setTimeout(resolve, 150));
    const result = await stt.startListening(lesson.session_id, activity);
    if (!result || !result.raw_transcript.trim()) {
      const message = stt.error || "Oops! I couldn't hear you 😊 Try again!";
      setError(message);
      setAvatar({ state: "encouraging", message, speak: true, animationEffect: "gentle_hint" });
      return;
    }
    setTranscript(result.raw_transcript);
    if (hasGuideSpeechIntent(result.raw_transcript)) {
      await askToddlerGuide(result.raw_transcript.trim(), true);
      return;
    }
    await submitAnswer(result.resolved_answer || result.normalized || result.raw_transcript, result.raw_transcript);
  }

  async function showHelp() {
    await askToddlerGuide("I don't understand. Show me and count each item with me.", true);
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

      <div data-guide-id="toddler-activity" className={`surface-panel grid gap-5 rounded-[2rem] p-5 text-center ${highlightId === "toddler-activity" ? "guide-glow" : ""}`}>
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
                  <span
                    key={`${item}-${index}`}
                    data-visual-id={`visual-item-${index}`}
                    data-count-label={countGuideEnabled ? index + 1 : undefined}
                    className={`grid h-24 w-24 place-items-center rounded-[2rem] bg-white text-5xl font-black shadow-soft ${visualGuideClass(visualAction, `visual-item-${index}`)}`}
                  >
                    {item}
                  </span>
                ))}
              </div>
            ) : null}
            <button
              type="button"
              disabled={busy || tts.speaking}
              onClick={showHelp}
              className="pressable rounded-full bg-sky px-6 py-4 text-xl font-black text-white shadow-soft disabled:opacity-60"
            >
              Show me &amp; explain
            </button>
          </div>
        ) : null}

        {activityAcceptsVoice(activity) ? (
          <div data-guide-id="toddler-microphone" className={`grid justify-items-center gap-3 rounded-[2rem] bg-sunshine/20 p-5 ${highlightId === "toddler-microphone" ? "guide-glow" : ""}`}>
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
          <div data-guide-id="toddler-choices" className={`grid gap-3 sm:grid-cols-3 ${highlightId === "toddler-choices" ? "guide-glow" : ""}`}>
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
