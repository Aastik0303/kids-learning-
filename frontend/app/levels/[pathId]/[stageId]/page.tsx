"use client";

import { useEffect, useState } from "react";
import { use } from "react";
import Link from "next/link";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { VoiceLearningSession } from "@/components/learning/VoiceLearningSession";
import { AppShell } from "@/components/shared/AppShell";
import type { VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import type { VisualGuideAction } from "@/components/guide/VisualGuideRenderer";
import { linearAdventurePath, pathSummaries } from "@/data/prototype";
import { avatarForLearningResult } from "@/services/avatar";
import { activityQuestion, GUIDE_TARGETS, guideAgent, isSafeGuideTarget, progressContext, visualTargetsForActivity } from "@/services/guide";
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
  const { setAvatar } = useAvatar();

  async function prepareQuestionGuide(activity: NonNullable<LearningResponse["activity"]>, sessionId: string, stored = child, updateSpokenMessage = false) {
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
    setGuideMessage(guide.message);
    setAvatar({ ...guide.avatar, speak: false });
    setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
    setVisualAction(guide.visual_action);
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

  async function choose(answer: string) {
    if (!learning) return;
    let delayNextQuestion = false;
    setBusy(true);
    setError("");
    setAvatar({ state: "thinking", message: "Let me check that...", animationEffect: "none", durationMs: null });
    try {
      const answeredActivity = learning.activity;
      const next = await answerLearning(learning.session_id, answer);
      if (child) {
        const fresh = await getProgress(child.child_id);
        saveChild(fresh.child);
        setChild(fresh.child);
      }
      if (next.is_correct === false && answeredActivity) {
        setLearning(next);
        setVoiceState("incorrect");
        const localHint = next.attempt_number > 1 ? "Almost there! Count slowly, then say it again." : "Good try! Look closely and count slowly.";
        setVoiceState("re_explaining");
        setGuideMessage(localHint);
        setAvatar({ state: "encouraging", message: localHint, animationEffect: "gentle_hint", durationMs: null });
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
          setGuideMessage(guide.message);
          setAvatar({ ...guide.avatar, speak: false });
          setHighlightId(isSafeGuideTarget(guide.ui_action.target) ? guide.ui_action.target : null);
          setVisualAction(guide.visual_action);
        });
        return;
      }
      if (next.is_correct) setVoiceState("correct");
      setAvatar(next.avatar ?? avatarForLearningResult(next));
      if (next.is_correct && next.activity && !next.complete) {
        setHighlightId(null);
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
            disabled={busy}
            highlightId={highlightId}
            visualAction={visualAction}
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
