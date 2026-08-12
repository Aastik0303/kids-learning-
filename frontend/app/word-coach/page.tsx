"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AIAvatar } from "@/components/avatar/AIAvatar";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { AppShell } from "@/components/shared/AppShell";
import { coachWords, spellWord } from "@/data/wordCoach";
import { secondTryEncouragement } from "@/services/guide";
import { captureVoiceAnswer, hasGuideSpeechIntent } from "@/services/speech";

const SCORE_KEY = "little-learning-word-coach-score";

function cleanWord(value: string) {
  return value.toLowerCase().replace(/[^a-z]/g, "");
}

function matchesWord(rawTranscript: string, resolvedAnswer: string, expectedWord: string) {
  const expected = cleanWord(expectedWord);
  const tokens: string[] = rawTranscript.toLowerCase().match(/[a-z]+/g) ?? [];
  const spokenLetters = tokens.filter((token) => token.length === 1).join("");
  return cleanWord(resolvedAnswer) === expected || tokens.includes(expected) || spokenLetters === expected;
}

export default function WordCoachPage() {
  const [wordIndex, setWordIndex] = useState(0);
  const [score, setScore] = useState(0);
  const [busy, setBusy] = useState(true);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [feedback, setFeedback] = useState("");
  const [wrongAttempts, setWrongAttempts] = useState(0);
  const { state, effect, isSpeaking, setAvatar, speakMessageAsync, stopSpeaking } = useAvatar();

  const currentWord = coachWords[wordIndex % coachWords.length];
  const letters = useMemo(() => spellWord(currentWord.word), [currentWord.word]);
  const spelling = letters.join(", ");

  useEffect(() => {
    const storedScore = Number(window.localStorage.getItem(SCORE_KEY));
    if (Number.isFinite(storedScore) && storedScore > 0) setScore(storedScore);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const lesson = `${currentWord.word} means ${currentWord.spokenHindi} in Hindi. Spell ${currentWord.word}: ${spelling}. Now say ${currentWord.word}.`;
    setBusy(true);
    setTranscript("");
    setTypedAnswer("");
    setFeedback("");
    setWrongAttempts(0);
    setAvatar({ state: "storytelling", message: lesson, speak: false, animationEffect: "story_transition", durationMs: null });
    speakMessageAsync(lesson).then(() => {
      if (cancelled) return;
      setBusy(false);
      setAvatar({ state: "listening", message: `Your turn. Say ${currentWord.word}.`, speak: false, animationEffect: "none", durationMs: null });
    });
    return () => {
      cancelled = true;
      stopSpeaking();
    };
  }, [currentWord.id, currentWord.spokenHindi, currentWord.word, setAvatar, speakMessageAsync, spelling, stopSpeaking]);

  async function replayLesson() {
    if (busy || listening) return;
    setBusy(true);
    const lesson = `${currentWord.word} means ${currentWord.spokenHindi} in Hindi. ${spelling}. Say ${currentWord.word}.`;
    setAvatar({ state: "speaking", message: lesson, speak: false, animationEffect: "pulse", durationMs: null });
    await speakMessageAsync(lesson);
    setBusy(false);
    setAvatar({ state: "listening", message: `Now say ${currentWord.word}.`, speak: false, animationEffect: "none", durationMs: null });
  }

  async function checkAnswer(rawAnswer: string, resolvedAnswer = rawAnswer) {
    const heard = rawAnswer.trim();
    if (!heard) {
      const message = "I could not hear a word. Please try again.";
      setFeedback(message);
      setAvatar({ state: "encouraging", message, speak: true, animationEffect: "gentle_hint", durationMs: null });
      return;
    }

    setTranscript(heard);
    if (hasGuideSpeechIntent(heard)) {
      const help = `Say ${currentWord.word}. It means ${currentWord.spokenHindi}. Spell it ${spelling}.`;
      setFeedback(help);
      setAvatar({ state: "speaking", message: help, speak: false, animationEffect: "pulse", durationMs: null });
      await speakMessageAsync(help);
      return;
    }

    if (!matchesWord(heard, resolvedAnswer, currentWord.word)) {
      const nextAttempt = wrongAttempts + 1;
      setWrongAttempts(nextAttempt);
      const retry = nextAttempt === 1
        ? secondTryEncouragement()
        : `Let us practise it together: ${currentWord.word}. ${spelling}.`;
      setFeedback(nextAttempt === 1 ? retry : `I heard “${heard}”. Let us practise once, then try again.`);
      setAvatar({ state: "encouraging", message: retry, speak: false, animationEffect: "gentle_hint", durationMs: null });
      await speakMessageAsync(retry);
      return;
    }

    const nextScore = score + 10;
    setWrongAttempts(0);
    setScore(nextScore);
    window.localStorage.setItem(SCORE_KEY, String(nextScore));
    const success = `Yes! ${currentWord.word} is correct. Ten points!`;
    setFeedback(success);
    setAvatar({ state: "celebrating", message: success, speak: false, animationEffect: "star_burst", durationMs: null });
    await speakMessageAsync(success);
    setWordIndex((current) => (current + 1) % coachWords.length);
  }

  async function startListening() {
    if (busy || listening) return;
    stopSpeaking();
    setBusy(true);
    setListening(true);
    setTranscript("");
    setFeedback("");
    setAvatar({ state: "listening", message: "I am listening...", speak: false, animationEffect: "pulse", durationMs: null });
    try {
      const result = await captureVoiceAnswer({
        sessionId: "word-coach",
        activityId: `word-${currentWord.id}`,
        answerType: "repeat_word",
        correctAnswer: currentWord.word,
        acceptedAnswers: [currentWord.word],
        timeoutMs: 8000
      });
      await checkAnswer(result.raw_transcript, result.resolved_answer);
    } catch (voiceError) {
      const message = voiceError instanceof Error ? voiceError.message : "Voice input did not work. Please try again.";
      setFeedback(message);
      setAvatar({ state: "encouraging", message, speak: true, animationEffect: "gentle_hint", durationMs: null });
    } finally {
      setListening(false);
      setBusy(false);
    }
  }

  async function submitTypedAnswer(event: FormEvent) {
    event.preventDefault();
    if (!typedAnswer.trim() || busy || listening) return;
    setBusy(true);
    try {
      await checkAnswer(typedAnswer, typedAnswer);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="AI Word Coach">
      <section className="surface-panel mx-auto grid w-full max-w-5xl gap-5 rounded-[2rem] p-5 sm:p-7">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-ink/10 pb-5">
          <div>
            <p className="text-sm font-black uppercase text-leaf">English + Hindi</p>
            <h1 className="text-4xl font-black text-ink sm:text-5xl">AI Word Coach</h1>
          </div>
          <div className="rounded-2xl bg-sunshine px-6 py-4 text-center shadow-soft" aria-live="polite">
            <p className="text-sm font-black uppercase text-ink/60">Score</p>
            <p className="text-4xl font-black text-ink">{score}</p>
          </div>
        </header>

        <div className="grid items-center gap-6 lg:grid-cols-[15rem_1fr]">
          <div className="grid justify-items-center gap-3">
            <div className="h-48 w-48">
              <AIAvatar state={state} effect={effect} isSpeaking={isSpeaking} />
            </div>
            <span className="text-7xl" aria-hidden="true">{currentWord.emoji}</span>
          </div>

          <div className="grid min-w-0 gap-5 text-center lg:text-left">
            <div>
              <p className="text-6xl font-black text-ink sm:text-7xl">{currentWord.word}</p>
              <p className="mt-2 text-4xl font-black text-berry" lang="hi">{currentWord.hindi}</p>
              <p className="mt-1 text-lg font-bold text-ink/60">{currentWord.spokenHindi}</p>
            </div>

            <div className="flex flex-wrap justify-center gap-2 lg:justify-start" aria-label={`Spelling: ${spelling}`}>
              {letters.map((letter, index) => (
                <span key={`${letter}-${index}`} className="grid h-14 w-12 place-items-center rounded-lg bg-[#f7fbff] text-2xl font-black text-sky shadow-soft">
                  {letter}
                </span>
              ))}
            </div>

            <div className="grid gap-3 sm:grid-cols-[auto_1fr] sm:items-center">
              <button
                type="button"
                onClick={startListening}
                disabled={busy || listening}
                className="pressable grid min-h-24 place-items-center rounded-2xl bg-leaf px-7 py-4 text-xl font-black text-white shadow-soft disabled:opacity-60"
              >
                <span className="text-3xl" aria-hidden="true">🎤</span>
                {listening ? "Listening..." : "Say the word"}
              </button>
              <button
                type="button"
                onClick={replayLesson}
                disabled={busy || listening}
                className="pressable min-h-16 rounded-2xl bg-sky px-6 py-4 text-lg font-black text-white shadow-soft disabled:opacity-60"
              >
                <span aria-hidden="true">🔊</span> Repeat meaning & spelling
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-3 border-t border-ink/10 pt-5">
          {transcript ? <p className="text-center text-lg font-bold text-ink/70">I heard: <strong className="text-ink">{transcript}</strong></p> : null}
          {feedback ? <p className="rounded-2xl bg-[#eef8f2] px-5 py-4 text-center text-lg font-black text-ink" aria-live="polite">{feedback}</p> : null}
          <form onSubmit={submitTypedAnswer} className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <input
              value={typedAnswer}
              onChange={(event) => setTypedAnswer(event.target.value)}
              disabled={busy || listening}
              className="min-h-14 min-w-0 rounded-2xl border-2 border-leaf/20 bg-white px-5 py-3 text-lg font-bold text-ink outline-none focus:border-sky"
              placeholder="Type the English word"
              aria-label="Type the English word"
            />
            <button type="submit" disabled={busy || listening || !typedAnswer.trim()} className="pressable min-h-14 rounded-2xl bg-ink px-7 py-3 text-lg font-black text-white disabled:opacity-50">
              Check
            </button>
          </form>
        </div>
      </section>
    </AppShell>
  );
}
