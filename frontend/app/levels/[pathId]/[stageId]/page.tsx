"use client";

import { useEffect, useRef, useState } from "react";
import { use } from "react";
import Link from "next/link";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { VoiceLearningSession } from "@/components/learning/VoiceLearningSession";
import { AppShell } from "@/components/shared/AppShell";
import type { VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import type { VisualGuideAction } from "@/components/guide/VisualGuideRenderer";
import { linearAdventurePath, pathSummaries } from "@/data/prototype";
import { avatarForLearningResult } from "@/services/avatar";
import { activityQuestion, askGuideQuestion, GUIDE_TARGETS, guideAgent, isSafeGuideTarget, progressContext, secondTryEncouragement, visualTargetsForActivity } from "@/services/guide";
import { answerLearning, startLearning } from "@/services/learning";
import { getOrCreateGuestChild, saveChild } from "@/services/session";
import { getProgress } from "@/services/child";
import type { ChildProfile, LearningResponse } from "@/types";

function pathTotal(pathId: string) {
  return pathSummaries.find((path) => path.path_id === pathId)?.total_stages ?? (pathId === "mixed_final" ? 3 : 8);
}

function pathComplete(child: ChildProfile, pathId: string) {
  const total = pathTotal(pathId);
  const progress = child.path_progress[pathId];
  return child.completed_paths.includes(pathId) || (progress?.completed_stages.length ?? 0) >= total;
}

function activePath(child: ChildProfile) {
  return linearAdventurePath.find((pathId) => !pathComplete(child, pathId)) ?? null;
}

function nextStage(child: ChildProfile, pathId: string) {
  const total = pathTotal(pathId);
  const completed = new Set(child.path_progress[pathId]?.completed_stages ?? []);
  for (let stage = 1; stage <= total; stage += 1) {
    if (!completed.has(stage)) return stage;
  }
  return total;
}

function localQuestionMessage(prompt: string) {
  return `Look carefully. ${prompt} Say your answer after I finish.`;
}

export default function StagePage({ params }: { params: Promise<{ pathId: string; stageId: string }> }) {
  const { pathId, stageId } = use(params);
  const [child, setChild] = useState<ChildProfile | null>(null);
  const [learning, setLearning] = useState<LearningResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceInteractionState>("idle");
  const [guideMessage, setGuideMessage] = useState("");
  const [visualAction, setVisualAction] = useState<VisualGuideAction>(null);
  const [countGuideEnabled, setCountGuideEnabled] = useState(false);
  const guideRequestRef = useRef(0);
  const answerInFlightRef = useRef(false);
  const { setAvatar } = useAvatar();

  async function prepareQuestionGuide(activity: NonNullable<LearningResponse["activity"]>, sessionId: string, stored = child, updateSpokenMessage = false) {
    const requestId = ++guideRequestRef.current;
    const currentChild = stored ?? getOrCreateGuestChild();
    setVoiceState("explaining");
    const guide = await guideAgent({
      session_id: sessionId,
      child_id: currentChild.child_id,
      mode: "learning",
      event: "LEVEL_QUESTION_LOADED",
      route: `/levels/${pathId}/${stageId}`,
      screen: "learning_activity",
      feature: pathId,
      age_group: currentChild.age_group,
      preferred_language: currentChild.preferred_language,
      question: activityQuestion(activity, { topic: pathId, concept: activity.type }),
      progress: progressContext(currentChild, pathId, `Level ${stageId}`),
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
    const stored = getOrCreateGuestChild();
    setChild(stored);
    const stageNumber = Number(stageId);
    const currentPath = activePath(stored);
    if (currentPath === null) {
      setError("Your certificate celebration is ready.");
      setAvatar({ state: "celebrating", message: "Your certificate celebration is ready!", animationEffect: "certificate_celebration" });
      return;
    }
    if (pathId !== currentPath || stageNumber !== nextStage(stored, pathId)) {
      setError("Follow the glowing node on the adventure map.");
      setAvatar({ state: "encouraging", message: "Follow the glowing node on the adventure map.", animationEffect: "gentle_hint" });
      return;
    }
    const progress = stored.path_progress[pathId];
    if (progress && !progress.unlocked_stages.includes(stageNumber)) {
      setError("This stage is still locked. Finish the bright current stage first.");
      setAvatar({ state: "encouraging", message: "This stage is still locked. Finish the bright current stage first.", animationEffect: "gentle_hint" });
      return;
    }
    setAvatar({ state: "thinking", message: "Getting your stage ready...", animationEffect: "story_transition", durationMs: null });
    startLearning(stored.child_id, pathId, stageNumber)
      .then((response) => {
        if (response.activity) {
          setGuideMessage(localQuestionMessage(response.activity.prompt));
          setLearning(response);
          prepareQuestionGuide(response.activity, response.session_id, stored);
        } else {
          setAvatar(response.avatar ?? avatarForLearningResult(response));
          setLearning(response);
        }
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : "Something went wrong. Let us try again.";
        setError(message);
        setAvatar({ state: "error_fallback", message, animationEffect: "none" });
      });
  }, [pathId, setAvatar, stageId]);

  async function askCurrentGuide(question: string) {
    const activity = learning?.activity;
    if (!learning || !activity || busy) return;

    setBusy(true);
    setError("");
    setVoiceState("re_explaining");
    setAvatar({ state: "thinking", message: "Let me help with that...", animationEffect: "pulse", durationMs: null });
    const requestId = ++guideRequestRef.current;
    try {
      const guide = await askGuideQuestion({
        question,
        route: `/levels/${pathId}/${stageId}`,
        sessionId: learning.session_id,
        screen: "learning_activity",
        activity,
        topic: pathId,
        attempt: learning.attempt_number
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
    if (!learning || busy || answerInFlightRef.current) return;
    answerInFlightRef.current = true;
    // Invalidate any explanation that belongs to the previous attempt.
    guideRequestRef.current += 1;
    let delayNextQuestion = false;
    setBusy(true);
    setError("");
    setAvatar({ state: "thinking", message: "Let me check that...", animationEffect: "none", durationMs: null });
    try {
      const answeredActivity = learning.activity;
      const next = await answerLearning(learning.session_id, answer);
      if (child) {
        // Progress refresh is supplementary. A network failure here must not
        // leave the UI on an activity the backend has already completed.
        void getProgress(child.child_id).then((fresh) => {
          saveChild(fresh.child);
          setChild(fresh.child);
        }).catch(() => undefined);
      }
      if (next.is_correct === false && next.question_changed && next.activity) {
        setLearning(next);
        setHighlightId(null);
        setVisualAction(null);
        setCountGuideEnabled(false);
        setVoiceState("re_explaining");
        setGuideMessage(next.feedback);
        setAvatar({ state: "encouraging", message: next.feedback, speak: true, animationEffect: "story_transition", durationMs: null });
        await prepareQuestionGuide(next.activity, next.session_id, child);
        return;
      }
      if (next.is_correct === false && answeredActivity) {
        setLearning(next);
        setVoiceState("incorrect");
        const localHint = next.attempt_number === 1
          ? secondTryEncouragement()
          : "Almost there! Look carefully, then say it again.";
        setVoiceState("re_explaining");
        setGuideMessage(localHint);
        setAvatar({ state: "encouraging", message: localHint, animationEffect: "gentle_hint", durationMs: null });
        const requestId = ++guideRequestRef.current;
        guideAgent({
          session_id: next.session_id,
          child_id: next.child_id,
          mode: "learning",
          event: "LEVEL_ANSWER_INCORRECT",
          route: `/levels/${pathId}/${stageId}`,
          screen: "learning_activity",
          feature: pathId,
          age_group: child?.age_group ?? "3-6",
          preferred_language: child?.preferred_language ?? "en",
          question: activityQuestion(answeredActivity, {
            topic: pathId,
            concept: answeredActivity.type,
            child_answer: answer,
            attempt: next.attempt_number,
            recent_answers: [answer]
          }),
          progress: progressContext(child, pathId, `Level ${stageId}`),
          available_actions: ["show_hint", "highlight", "repeat_instruction"],
          available_targets: [GUIDE_TARGETS.COUNTING_OBJECTS, GUIDE_TARGETS.QUESTION_AREA, GUIDE_TARGETS.VOICE_ANSWER_AREA, GUIDE_TARGETS.MICROPHONE_BUTTON],
          allowed_visual_targets: visualTargetsForActivity(answeredActivity)
        }).then((guide) => {
          if (requestId !== guideRequestRef.current) return;
          setGuideMessage(guide.message);
          setAvatar({ ...guide.avatar, speak: false });
          if (next.attempt_number >= 2) {
            setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
            setVisualAction(guide.visual_action);
            setCountGuideEnabled(true);
          } else {
            setHighlightId(null);
            setVisualAction(null);
            setCountGuideEnabled(false);
          }
        });
        return;
      }
      if (next.is_correct) setVoiceState("correct");
      setAvatar(next.avatar ?? avatarForLearningResult(next));
      if (next.is_correct && next.activity && !next.complete) {
        setHighlightId(null);
        setVisualAction(null);
        setCountGuideEnabled(false);
        delayNextQuestion = true;
        setLearning({ ...next, activity: null });
        window.setTimeout(() => {
          setGuideMessage(localQuestionMessage(next.activity!.prompt));
          setLearning(next);
          prepareQuestionGuide(next.activity!, next.session_id, child);
          setBusy(false);
        }, 650);
        return;
      }
      if (next.complete) {
        setLearning(next);
        guideAgent({
          session_id: next.session_id,
          child_id: next.child_id,
          mode: "learning",
          event: "LEVEL_COMPLETED",
          route: `/levels/${pathId}/${stageId}`,
          screen: "level_complete",
          feature: pathId,
          age_group: child?.age_group ?? "3-6",
          preferred_language: child?.preferred_language ?? "en",
          progress: progressContext(child, pathId, `Level ${stageId}`),
          available_actions: ["highlight"],
          available_targets: [GUIDE_TARGETS.OPEN_LEVELS, GUIDE_TARGETS.CONTINUE_ADVENTURE]
        }).then((guide) => {
          setAvatar(guide.avatar);
          setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
        });
        return;
      }
      setLearning(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Let us try again.");
    } finally {
      answerInFlightRef.current = false;
      if (!delayNextQuestion) {
        setBusy(false);
      }
    }
  }

  return (
    <AppShell>
      <div className="grid gap-5">
        <div className="surface-panel flex flex-wrap items-center justify-between gap-3 rounded-[2rem] p-5">
          <div>
            <p className="text-sm font-black uppercase text-leaf">Stage {stageId}</p>
            <h1 className="text-4xl font-black capitalize text-ink sm:text-5xl">{pathId.replace("_", " ")} Level</h1>
          </div>
          <Link className="pressable rounded-full bg-white px-4 py-3 font-black text-ink shadow-soft" href="/levels">
            Adventure Map
          </Link>
        </div>
        {learning ? <p className="surface-panel rounded-[2rem] p-5 text-xl font-bold text-ink">{learning.tutor_response}</p> : null}
        {error ? <p className="rounded-[2rem] bg-berry/10 p-5 font-bold text-berry shadow-soft">{error}</p> : null}
        {learning?.feedback ? (
          <p className={`rounded-[2rem] p-5 text-xl font-black shadow-soft ${learning.is_correct ? "bg-leaf text-white" : "bg-sunshine text-ink"}`}>
            {learning.feedback}
          </p>
        ) : null}
        {learning?.activity ? (
          <VoiceLearningSession
            activity={learning.activity}
            sessionId={learning.session_id}
            guideMessage={guideMessage || learning.activity.prompt}
            voiceState={voiceState}
            onVoiceStateChange={setVoiceState}
            onAnswer={choose}
            onGuideQuestion={askCurrentGuide}
            disabled={busy}
            highlightId={highlightId}
            visualAction={visualAction}
            countGuideEnabled={countGuideEnabled}
            showOptionsWithMicrophone={["colours", "colors", "shapes"].includes(pathId.toLowerCase())}
          />
        ) : null}
        {learning?.complete ? (
          <div className="surface-panel grid gap-3 rounded-[2rem] p-6 text-center">
            <h2 className="text-4xl font-black text-ink">Level complete</h2>
            <p className="text-xl font-bold text-ink/70">Stars earned: {learning.stars_earned}</p>
            <Link data-guide-id="open-levels" className={`pressable rounded-3xl bg-leaf px-5 py-4 text-center text-xl font-black text-white shadow-soft ${highlightId === "open-levels" ? "guide-glow" : ""}`} href="/levels">
              Continue Adventure
            </Link>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
