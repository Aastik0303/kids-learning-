"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { VoicePracticeSession } from "@/components/practice/VoicePracticeSession";
import { AppShell } from "@/components/shared/AppShell";
import type { VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import type { VisualGuideAction } from "@/components/guide/VisualGuideRenderer";
import { avatarForPage, avatarForPracticeResult } from "@/services/avatar";
import { activityQuestion, GUIDE_TARGETS, guideAgent, isSafeGuideTarget, progressContext, visualTargetsForActivity } from "@/services/guide";
import { answerPractice, startPractice } from "@/services/practice";
import { getOrCreateGuestChild } from "@/services/session";
import type { Activity } from "@/types";

function localQuestionMessage(prompt: string) {
  return `Look carefully. ${prompt} Say your answer after I finish.`;
}

export default function PracticeSessionPage({ params }: { params: Promise<{ topic: string }> }) {
  const { topic } = use(params);
  const [sessionId, setSessionId] = useState("");
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
  const [loading, setLoading] = useState(true);
  const { setAvatar } = useAvatar();

  async function explainQuestion(activity: Activity, currentSessionId: string, updateSpokenMessage = false) {
    const child = getOrCreateGuestChild();
    setVoiceState("explaining");
    const guide = await guideAgent({
      session_id: currentSessionId,
      child_id: child.child_id,
      mode: "practice",
      event: "PRACTICE_QUESTION_LOADED",
      route: `/practice/${topic}`,
      screen: "practice_session",
      feature: `${topic}_practice`,
      age_group: child.age_group,
      preferred_language: child.preferred_language,
      question: activityQuestion(activity, { topic, concept: activity.type, attempt: wrongAttempts[activity.activity_id] ?? 0 }),
      progress: progressContext(child, topic, null),
      available_actions: ["highlight", "repeat_instruction"],
      available_targets: [GUIDE_TARGETS.QUESTION_AREA, GUIDE_TARGETS.COUNTING_OBJECTS, GUIDE_TARGETS.VOICE_ANSWER_AREA, GUIDE_TARGETS.MICROPHONE_BUTTON],
      allowed_visual_targets: visualTargetsForActivity(activity)
    });
    setGuideMessage(guide.message);
    setAvatar({ ...guide.avatar, speak: false });
    setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
    setVisualAction(guide.visual_action);
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setAvatar(avatarForPage("practice"));
    const child = getOrCreateGuestChild();
    startPractice(child.child_id, topic).then((session) => {
      if (!active) return;
      setSessionId(session.practice_session_id);
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

  async function choose(answer: string) {
    const activity = activities[index];
    if (!activity || busy) return;
    setBusy(true);
    setAvatar({ state: "thinking", message: "Checking your answer...", animationEffect: "none", durationMs: null });
    const result = await answerPractice(sessionId, activity.activity_id, answer);
    setFeedback(result.feedback);
    setHint(result.hint);
    if (result.is_correct) {
      setHighlightId(null);
      setWrongAttempts((current) => ({ ...current, [activity.activity_id]: 0 }));
      setVoiceState("correct");
      setAvatar(result.avatar ?? avatarForPracticeResult(result));
      if (index + 1 >= activities.length) {
        const child = getOrCreateGuestChild();
        guideAgent({
          session_id: sessionId,
          child_id: child.child_id,
          mode: "practice",
          event: "PRACTICE_COMPLETED",
          route: `/practice/${topic}`,
          screen: "practice_complete",
          feature: `${topic}_practice`,
          age_group: child.age_group,
          preferred_language: child.preferred_language,
          progress: progressContext(child, topic, null),
          available_actions: ["highlight"],
          available_targets: [GUIDE_TARGETS.MORE_PRACTICE, GUIDE_TARGETS.OPEN_LEVELS]
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
    setWrongAttempts((current) => ({ ...current, [activity.activity_id]: nextAttempt }));
    setVoiceState("incorrect");
    const localHint = nextAttempt > 1 ? "Almost there! Count slowly, then say it again." : "Good try! Look closely and count slowly.";
    setVoiceState("re_explaining");
    setGuideMessage(localHint);
    setAvatar({ state: "encouraging", message: localHint, animationEffect: "gentle_hint", durationMs: null });
    const child = getOrCreateGuestChild();
    guideAgent({
      session_id: sessionId,
      child_id: child.child_id,
      mode: "practice",
      event: "PRACTICE_ANSWER_INCORRECT",
      route: `/practice/${topic}`,
      screen: "practice_session",
      feature: `${topic}_practice`,
      age_group: child.age_group,
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
      setGuideMessage(guide.message);
      setAvatar({ ...guide.avatar, speak: false });
      setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
      setVisualAction(guide.visual_action);
    });
    setBusy(false);
  }

  const activity = activities[index];

  return (
    <AppShell>
      <div className="grid gap-5">
        <div className="surface-panel flex flex-wrap items-center justify-between gap-3 rounded-[2rem] p-5">
          <div>
            <p className="text-sm font-black uppercase text-sky">Practice</p>
            <h1 className="text-4xl font-black capitalize text-ink sm:text-5xl">{topic.replace("-", " ")} Practice</h1>
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
            disabled={busy}
            highlightId={highlightId}
            visualAction={visualAction}
          />
        ) : (
          <section className="surface-panel grid gap-4 rounded-[2rem] p-6 text-center">
            <h2 className="text-4xl font-black text-ink sm:text-5xl">Practice complete</h2>
            <p className="text-xl font-bold text-ink/70">Great effort. You can try another topic or open Levels.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Link data-guide-id="more-practice" className={`pressable rounded-3xl bg-sky px-5 py-4 text-xl font-black text-white shadow-soft ${highlightId === "more-practice" ? "guide-glow" : ""}`} href="/practice">
                More Practice
              </Link>
              <Link data-guide-id="open-levels" className={`pressable rounded-3xl bg-leaf px-5 py-4 text-xl font-black text-white shadow-soft ${highlightId === "open-levels" ? "guide-glow" : ""}`} href="/levels">
                Open Levels
              </Link>
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}
