"use client";

import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { TraceCanvas } from "@/components/learning/TraceCanvas";
import { VisualTile } from "@/components/shared/VisualTile";
import { SpeechErrorMessage } from "@/components/voice/SpeechErrorMessage";
import { VoiceRecorder } from "@/components/voice/VoiceRecorder";
import { VoiceStateIndicator, type VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import { VoiceTranscriptPreview } from "@/components/voice/VoiceTranscriptPreview";
import type { Activity, ExperienceMode } from "@/types";
import { learningTargetStyle, limitChoices, showsText } from "@/lib/experience";
import { displayToken, isTextToken, visualIcon } from "@/lib/visualIcon";

type Props = {
  activity: Activity;
  mode: ExperienceMode;
  sessionId: string;
  disabled?: boolean;
  /** null before the first answer of this activity. */
  isCorrect?: boolean | null;
  attemptNumber?: number;
  hint?: string;
  onAnswer: (answer: string) => void;
};

/**
 * Renders one activity according to how it is answered.
 *
 * Only about two thirds of the authored content is tap-a-choice. The rest is
 * watched, said aloud, written, or done away from the screen with a grown-up —
 * rendering a choice grid for those would show a child an empty box.
 *
 * The presentation matches Practice on purpose: same mission card, same picture
 * tiles, same microphone. A lesson and its practice are the same content, so
 * they should not look like two different apps.
 *
 * The question itself is always shown, in both modes. It carries the emoji a
 * pre-reader actually reads, and it is spoken aloud either way. `early` mode
 * still keeps written words off the *answers* — a child should never have to
 * read "watermelon" to choose it.
 */
export function ActivityView({
  activity,
  mode,
  sessionId,
  disabled,
  isCorrect,
  attemptNumber = 0,
  hint,
  onAnswer
}: Props) {
  const withText = showsText(mode);
  const { setAvatar, speakMessage } = useAvatar();
  // Multi-answer match activities ("put the red things together") collect
  // several picks before submitting.
  const isMultiPick = Boolean(activity.correct_answer?.includes(","));
  const [picked, setPicked] = useState<string[]>([]);
  const [lastTried, setLastTried] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceInteractionState>("ready_to_listen");
  const [transcript, setTranscript] = useState("");
  const [speechError, setSpeechError] = useState("");

  useEffect(() => {
    setPicked([]);
    setLastTried(null);
    setTranscript("");
    setSpeechError("");
    setVoiceState("ready_to_listen");
  }, [activity.activity_id]);

  // After a second miss the answer is pointed out rather than only described.
  // A two-year-old cannot read a hint, so the help has to be something to look at.
  const wrong = isCorrect === false;
  const pointOutAnswer = wrong && attemptNumber >= 2;
  const answerTokens = new Set(
    (activity.correct_answer ?? "").split(",").map((part) => part.trim().toLowerCase())
  );

  function readPrompt() {
    setAvatar({ state: "speaking", message: activity.prompt, animationEffect: "none", durationMs: 4200 });
    speakMessage(activity.prompt);
  }

  const mission = (
    <div className="grid gap-4 rounded-[2rem] bg-[#f7fbff] p-4 sm:grid-cols-[7rem_1fr] sm:items-center">
      <div className="mascot-face min-h-28 rounded-[1.75rem]" />
      <div>
        <p className="text-sm font-black uppercase text-sky">🧩 Mini mission</p>
        <h2 id="question-area" className="mt-2 text-3xl font-black leading-tight text-ink sm:text-4xl">
          {activity.prompt}
        </h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full bg-leaf/10 px-4 py-2 text-sm font-black capitalize text-leaf">
            {activity.difficulty.replace(/_/g, " ")}
          </span>
          <span className="rounded-full bg-sunshine/40 px-4 py-2 text-sm font-black text-ink">⭐ Reward +3</span>
          <button
            type="button"
            onClick={readPrompt}
            className="pressable rounded-full bg-white px-4 py-2 text-sm font-black text-ink shadow-soft"
          >
            🔊 Voice
          </button>
        </div>
      </div>
    </div>
  );

  const visuals = activity.visual_items.length ? (
    <div className="flex min-h-36 flex-wrap items-center justify-center gap-4 rounded-[2rem] border border-sky/10 bg-[#f7fbff] p-5">
      {activity.visual_items.map((item, index) => (
        <VisualTile
          key={`${item}-${index}`}
          item={item}
          domId={`visual-item-${index}`}
          visualId={`visual-item-${index}`}
          highlightClass={
            pointOutAnswer && answerTokens.has(item.trim().toLowerCase()) ? "visual-guide-pulse" : ""
          }
        />
      ))}
    </div>
  ) : null;

  // Shown under the question whenever an answer was wrong, so the help is on
  // screen rather than only in a line of feedback further down the page.
  const helper = wrong ? (
    <div
      data-testid="wrong-answer-help"
      className="grid gap-1 rounded-[2rem] border-2 border-berry/25 bg-berry/5 p-4 text-center"
    >
      <p className="text-lg font-black text-berry">
        {pointOutAnswer ? "👀 Look — this is the one!" : "Not that one. Try again! 💪"}
      </p>
      {hint ? <p className="text-base font-bold text-ink/75">💡 {hint}</p> : null}
    </div>
  ) : null;

  // --- written with a finger ----------------------------------------------
  if (activity.type === "trace") {
    return (
      <section
        id="activity-area"
        data-testid="activity-area"
        data-answer-kind="presentational"
        className="surface-panel grid gap-5 rounded-[2rem] p-5 sm:p-6"
      >
        {mission}
        <TraceCanvas
          target={activity.trace_target ?? activity.visual_items[0] ?? "line"}
          minAccuracy={activity.min_accuracy ?? 0.5}
          disabled={disabled}
          onComplete={() => onAnswer("done")}
        />
      </section>
    );
  }

  // --- watched, or done off-screen ----------------------------------------
  if (activity.answer_kind === "presentational") {
    const isParentCard = activity.type === "parent_activity";
    return (
      <section
        id="activity-area"
        data-testid="activity-area"
        data-answer-kind="presentational"
        className="surface-panel grid gap-5 rounded-[2rem] p-5 sm:p-6"
      >
        {mission}
        {visuals}
        {isParentCard && activity.parent_note ? (
          <div data-surface="parent" className="rounded-[2rem] bg-[#f5f8ef] p-5">
            <p className="text-sm font-black uppercase text-leaf">👨‍👩‍👧 For the grown-up</p>
            <p className="mt-1 font-bold text-ink/80">{activity.parent_note}</p>
          </div>
        ) : null}
        <button
          type="button"
          disabled={disabled}
          onClick={() => onAnswer("done")}
          style={learningTargetStyle(mode)}
          data-testid="activity-done"
          className="pressable rounded-3xl bg-leaf px-6 py-4 text-xl font-black text-white shadow-soft disabled:opacity-50"
        >
          {isParentCard ? "🎉 We did it!" : "👉 Next"}
        </button>
      </section>
    );
  }

  // --- said aloud ---------------------------------------------------------
  if (activity.answer_kind === "spoken") {
    return (
      <section
        id="activity-area"
        data-testid="activity-area"
        data-answer-kind="spoken"
        className="surface-panel grid gap-5 rounded-[2rem] p-5 sm:p-6"
      >
        {mission}
        {visuals}
        {helper}
        <div className="grid gap-4 rounded-[2rem] bg-sunshine/20 p-5 text-center">
          <VoiceStateIndicator state={voiceState} />
          <VoiceRecorder
            sessionId={sessionId}
            activity={activity}
            state={voiceState}
            disabled={disabled || voiceState === "speaking"}
            onStateChange={setVoiceState}
            onTranscript={setTranscript}
            onSpeechError={setSpeechError}
            onVoiceAnswer={onAnswer}
          />
          <VoiceTranscriptPreview transcript={transcript} />
          <SpeechErrorMessage message={speechError} />
        </div>
        {speechError ? (
          // Speech can be unavailable — no permission, no browser support. The
          // lesson must not become a dead end because of it.
          <button
            type="button"
            disabled={disabled}
            onClick={() => onAnswer(activity.open_ended ? "spoken" : activity.correct_answer ?? "spoken")}
            style={learningTargetStyle(mode)}
            data-testid="activity-spoken-fallback"
            className="pressable rounded-3xl bg-sky px-6 py-4 text-xl font-black text-white shadow-soft disabled:opacity-50"
          >
            🙂 I said it out loud
          </button>
        ) : null}
      </section>
    );
  }

  // --- tap a choice -------------------------------------------------------
  const choices = limitChoices(activity.options, mode);
  return (
    <section
      id="activity-area"
      data-testid="activity-area"
      data-answer-kind="choice"
      className="surface-panel grid gap-5 rounded-[2rem] p-5 sm:p-6"
    >
      {mission}
      {visuals}
      {helper}
      <div
        id="answer-options"
        data-testid="answer-options"
        data-choice-count={choices.length}
        data-max-choices={mode.max_choices_per_screen}
        className={`grid gap-4 ${choices.length > 2 ? "grid-cols-3" : "grid-cols-1 sm:grid-cols-2"}`}
      >
        {choices.map((choice) => {
          const isPicked = picked.includes(choice);
          const missed = wrong && lastTried === choice;
          const isAnswer = pointOutAnswer && answerTokens.has(choice.trim().toLowerCase());
          return (
            <button
              key={choice}
              type="button"
              disabled={disabled}
              aria-pressed={isMultiPick ? isPicked : undefined}
              onClick={() => {
                if (isMultiPick) {
                  setPicked((current) =>
                    current.includes(choice)
                      ? current.filter((item) => item !== choice)
                      : [...current, choice]
                  );
                  return;
                }
                setLastTried(choice);
                onAnswer(choice);
              }}
              style={learningTargetStyle(mode)}
              data-testid="answer-option"
              data-state={isAnswer ? "answer" : missed ? "missed" : undefined}
              aria-label={choice}
              className={`pressable flex flex-col items-center justify-center gap-1 rounded-3xl border-2 p-4 font-black shadow-soft transition disabled:opacity-50 ${
                isPicked ? "bg-leaf text-white" : "bg-white"
              } ${isAnswer ? "visual-guide-pulse border-leaf" : missed ? "border-berry opacity-60" : "border-transparent hover:border-ink/10"}`}
            >
              <span aria-hidden className="text-5xl leading-none">
                {isTextToken(choice) ? displayToken(choice) : visualIcon(choice)}
              </span>
              {withText ? <span className="text-lg capitalize">{choice}</span> : null}
            </button>
          );
        })}
      </div>

      {isMultiPick ? (
        <button
          type="button"
          disabled={disabled || picked.length === 0}
          onClick={() => onAnswer(picked.join(","))}
          style={learningTargetStyle(mode)}
          data-testid="activity-submit"
          className="pressable rounded-3xl bg-leaf px-6 py-4 text-xl font-black text-white shadow-soft disabled:opacity-50"
        >
          ✅ That&apos;s my answer
        </button>
      ) : null}
    </section>
  );
}
