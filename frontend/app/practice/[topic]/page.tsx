"use client";

import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { VoicePracticeSession } from "@/components/practice/VoicePracticeSession";
import { AppShell } from "@/components/shared/AppShell";
import type { VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import type { VisualGuideAction } from "@/components/guide/VisualGuideRenderer";
import { avatarForPage, avatarForPracticeResult } from "@/services/avatar";
import { activityQuestion, askGuideQuestion, GUIDE_TARGETS, guideAgent, isSafeGuideTarget, progressContext, secondTryEncouragement, visualTargetsForActivity } from "@/services/guide";
import { answerPractice, startPractice } from "@/services/practice";
import { getChild } from "@/services/session";
import type { Activity } from "@/types";

function localQuestionMessage(prompt: string) {
  return `Look carefully. ${prompt} Say your answer after I finish.`;
}

export default function PracticeSessionPage({ params }: { params: Promise<{ topic: string }> }) {
  const { topic } = use(params);
  const [sessionId, setSessionId] = useState("");
  // The subject's own names, from the server. The route param is a subject_id,
  // so titling the page from it printed "ukg maths Practice" at a child.
  const [heading, setHeading] = useState("");
  const [easyLine, setEasyLine] = useState("");
  const [activities, setActivities] = useState<Activity[]>([]);
  const [index, setIndex] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [wrongAttempts, setWrongAttempts] = useState<Record<string, number>>({});
  const [voiceState, setVoiceState] = useState<VoiceInteractionState>("idle");
  const [guideMessage, setGuideMessage] = useState("");
  const [visualAction, setVisualAction] = useState<VisualGuideAction>(null);
  const [countGuideEnabled, setCountGuideEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const guideRequestRef = useRef(0);
  const answerInFlightRef = useRef(false);
  const { setAvatar } = useAvatar();

  async function explainQuestion(activity: Activity, currentSessionId: string, updateSpokenMessage = false) {
    const requestId = ++guideRequestRef.current;
    const child = getChild();
    if (!child) return;
    setVoiceState("explaining");
    const guide = await guideAgent({
      session_id: currentSessionId,
      child_id: child.child_id,
      mode: "practice",
      event: "PRACTICE_QUESTION_LOADED",
      route: `/practice/${topic}`,
      screen: "practice_session",
      feature: `${topic}_practice`,
      class_id: child.class_id,
      experience_mode: child.experience_mode,
      preferred_language: child.preferred_language,
      question: activityQuestion(activity, { topic, concept: activity.type, attempt: wrongAttempts[activity.activity_id] ?? 0 }),
      progress: progressContext(child, topic, null),
      available_actions: ["highlight", "repeat_instruction"],
      available_targets: [GUIDE_TARGETS.QUESTION_AREA, GUIDE_TARGETS.COUNTING_OBJECTS, GUIDE_TARGETS.VOICE_ANSWER_AREA, GUIDE_TARGETS.MICROPHONE_BUTTON],
      allowed_visual_targets: visualTargetsForActivity(activity)
    });
    if (requestId !== guideRequestRef.current) return;
    setGuideMessage(guide.message);
    setAvatar({ ...guide.avatar, speak: false });
    setHighlightId(null);
    setVisualAction(null);
    setCountGuideEnabled(false);
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setAvatar(avatarForPage("practice"));
    const child = getChild();
    if (!child) {
      setLoading(false);
      return;
    }
    startPractice(child.child_id, topic).then((session) => {
      if (!active) return;
      setSessionId(session.practice_session_id);
      setHeading(session.subject_fun_name ?? session.subject_title);
      setEasyLine(session.subject_easy_line ?? "");
      setActivities(session.activities);
      setIndex(0);
      setFeedback("");
      setHint(null);
      setWrongAttempts({});
      const first = session.activities[0];
      if (first) {
        setGuideMessage(localQuestionMessage(first.prompt));
        explainQuestion(first, session.practice_session_id);
      }
      setLoading(false);
    }).catch(() => {
      if (!active) return;
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [setAvatar, topic]);

  async function askCurrentGuide(question: string) {
    const activity = activities[index];
    if (!activity || busy) return;

    setBusy(true);
    setFeedback("");
    setHint(null);
    setVoiceState("re_explaining");
    setAvatar({ state: "thinking", message: "Let me help with that...", animationEffect: "pulse", durationMs: null });
    const requestId = ++guideRequestRef.current;
    try {
      const guide = await askGuideQuestion({
        question,
        route: `/practice/${topic}`,
        sessionId,
        screen: "practice_session",
        activity,
        topic,
        attempt: wrongAttempts[activity.activity_id] ?? 0
      });
      if (requestId !== guideRequestRef.current) return;
      setGuideMessage(guide.message);
      setAvatar({ ...guide.avatar, speak: false });
      setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
      setVisualAction(guide.visual_action);
      setCountGuideEnabled(true);
    } finally {
      setBusy(false);
    }
  }

  async function choose(answer: string) {
    const activity = activities[index];
    if (!activity || busy || answerInFlightRef.current) return;
    answerInFlightRef.current = true;
    // A late hint must never overwrite the result of a newer answer.
    guideRequestRef.current += 1;
    setBusy(true);
    setAvatar({ state: "thinking", message: "Checking your answer...", animationEffect: "none", durationMs: null });
    let result;
    try {
      result = await answerPractice(sessionId, activity.activity_id, answer);
    } catch (error) {
      const message = error instanceof Error ? error.message : "I could not check that answer. Please try again.";
      setFeedback(message);
      setAvatar({ state: "error_fallback", message, animationEffect: "none" });
      setBusy(false);
      answerInFlightRef.current = false;
      return;
    }
    setFeedback(result.feedback);
    setHint(result.hint);
    if (result.is_correct) {
      setHighlightId(null);
      setVisualAction(null);
      setCountGuideEnabled(false);
      setWrongAttempts((current) => ({ ...current, [activity.activity_id]: 0 }));
      setVoiceState("correct");
      setAvatar(result.avatar ?? avatarForPracticeResult(result));
      if (index + 1 >= activities.length) {
        const child = getChild();
    if (!child) return;
        guideAgent({
          session_id: sessionId,
          child_id: child.child_id,
          mode: "practice",
          event: "PRACTICE_COMPLETED",
          route: `/practice/${topic}`,
          screen: "practice_complete",
          feature: `${topic}_practice`,
          class_id: child.class_id,
          experience_mode: child.experience_mode,
          preferred_language: child.preferred_language,
          progress: progressContext(child, topic, null),
          available_actions: ["highlight"],
          available_targets: [GUIDE_TARGETS.MORE_PRACTICE, GUIDE_TARGETS.OPEN_SUBJECTS]
        }).then((guide) => {
          setAvatar(guide.avatar);
          setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
        });
      }
      setTimeout(() => {
        const nextIndex = index + 1;
        setIndex(nextIndex);
        setFeedback("");
        setHint(null);
        setBusy(false);
        answerInFlightRef.current = false;
        const nextActivity = activities[nextIndex];
        if (nextActivity) {
          setGuideMessage(localQuestionMessage(nextActivity.prompt));
          explainQuestion(nextActivity, sessionId);
        } else {
          setVoiceState("completed");
        }
      }, 650);
      return;
    }
    const nextAttempt = (wrongAttempts[activity.activity_id] ?? 0) + 1;
    const shouldChangeQuestion = (result.question_changed || nextAttempt >= 4) && activities.length > 1;
    setWrongAttempts((current) => ({ ...current, [activity.activity_id]: shouldChangeQuestion ? 0 : nextAttempt }));
    if (shouldChangeQuestion) {
      const nextIndex = (index + 1) % activities.length;
      const nextActivity = activities[nextIndex];
      const transitionMessage = "Let's try a different question now.";
      setFeedback(transitionMessage);
      setHint(null);
      setHighlightId(null);
      setVisualAction(null);
      setCountGuideEnabled(false);
      setVoiceState("re_explaining");
      setGuideMessage(transitionMessage);
      setAvatar({ state: "encouraging", message: transitionMessage, speak: true, animationEffect: "story_transition", durationMs: null });
      window.setTimeout(() => {
        setIndex(nextIndex);
        setFeedback("");
        setGuideMessage(localQuestionMessage(nextActivity.prompt));
        explainQuestion(nextActivity, sessionId);
        setBusy(false);
        answerInFlightRef.current = false;
      }, 650);
      return;
    }
    setVoiceState("incorrect");
    const localHint = nextAttempt === 1
      ? secondTryEncouragement()
      : "Almost there! Look carefully, then say it again.";
    setVoiceState("re_explaining");
    setGuideMessage(localHint);
    setAvatar({ state: "encouraging", message: localHint, animationEffect: "gentle_hint", durationMs: null });
    const child = getChild();
    if (!child) return;
    const requestId = ++guideRequestRef.current;
    guideAgent({
      session_id: sessionId,
      child_id: child.child_id,
      mode: "practice",
      event: "PRACTICE_ANSWER_INCORRECT",
      route: `/practice/${topic}`,
      screen: "practice_session",
      feature: `${topic}_practice`,
      class_id: child.class_id,
      experience_mode: child.experience_mode,
      preferred_language: child.preferred_language,
      question: activityQuestion(activity, {
        topic,
        concept: activity.type,
        child_answer: answer,
        attempt: nextAttempt,
        recent_answers: [answer]
      }),
      progress: progressContext(child, topic, null),
      available_actions: ["show_hint", "highlight", "repeat_instruction"],
      available_targets: [GUIDE_TARGETS.COUNTING_OBJECTS, GUIDE_TARGETS.QUESTION_AREA, GUIDE_TARGETS.VOICE_ANSWER_AREA, GUIDE_TARGETS.MICROPHONE_BUTTON],
      allowed_visual_targets: visualTargetsForActivity(activity)
    }).then((guide) => {
      if (requestId !== guideRequestRef.current) return;
      setGuideMessage(guide.message);
      setAvatar({ ...guide.avatar, speak: false });
      if (nextAttempt >= 2) {
        setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
        setVisualAction(guide.visual_action);
        setCountGuideEnabled(true);
      } else {
        setHighlightId(null);
        setVisualAction(null);
        setCountGuideEnabled(false);
      }
    });
    setBusy(false);
    answerInFlightRef.current = false;
  }

  const activity = activities[index];

  return (
    <AppShell>
      <div className="grid gap-5">
        <div className="surface-panel flex flex-wrap items-center justify-between gap-3 rounded-[2rem] p-5">
          <div>
            <p className="text-sm font-black uppercase text-sky">Practice</p>
            <h1 className="text-4xl font-black text-ink sm:text-5xl">{heading || "Practice"}</h1>
            {easyLine ? <p className="mt-1 font-bold text-ink/70">{easyLine}</p> : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-sunshine px-4 py-3 font-black text-ink">Question {Math.min(index + 1, activities.length)} of {activities.length || 1}</span>
            <Link className="pressable rounded-full bg-white px-4 py-3 font-black text-ink shadow-soft" href="/">
              Back Home
            </Link>
          </div>
        </div>

        {feedback ? (
          <div className="surface-panel rounded-[2rem] border-sunshine/30 bg-sunshine/90 p-5 text-xl font-black text-ink">
            <p>{feedback}</p>
            {hint ? <p className="mt-2 text-lg">{hint}</p> : null}
          </div>
        ) : null}

        {loading ? (
          <section className="surface-panel grid gap-3 rounded-[2rem] p-6 text-center">
            <h2 className="text-3xl font-black text-ink">Getting practice ready</h2>
            <p className="text-lg font-bold text-ink/70">Your first voice question is loading.</p>
          </section>
        ) : activity ? (
          <VoicePracticeSession
            activity={activity}
            sessionId={sessionId}
            guideMessage={guideMessage || activity.prompt}
            voiceState={voiceState}
            onVoiceStateChange={setVoiceState}
            onAnswer={choose}
            onGuideQuestion={askCurrentGuide}
            disabled={busy}
            highlightId={highlightId}
            visualAction={visualAction}
            countGuideEnabled={countGuideEnabled}
            showOptionsWithMicrophone={["colours", "colors", "shapes"].includes(topic.toLowerCase())}
          />
        ) : (
          <section className="surface-panel grid gap-4 rounded-[2rem] p-6 text-center">
            <h2 className="text-4xl font-black text-ink sm:text-5xl">Practice complete</h2>
            <p className="text-xl font-bold text-ink/70">Great effort. You can try another topic or open Levels.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Link data-guide-id="more-practice" className={`pressable rounded-3xl bg-sky px-5 py-4 text-xl font-black text-white shadow-soft ${highlightId === "more-practice" ? "guide-glow" : ""}`} href="/practice">
                More Practice
              </Link>
              <Link data-guide-id="open-subjects" className={`pressable rounded-3xl bg-leaf px-5 py-4 text-xl font-black text-white shadow-soft ${highlightId === "open-subjects" ? "guide-glow" : ""}`} href="/adventure">
                Open Levels
              </Link>
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}
