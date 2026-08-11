"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AIAvatar } from "@/components/avatar/AIAvatar";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { AppShell } from "@/components/shared/AppShell";
import { sentenceLessons, spellSentenceWord } from "@/data/sentenceCoach";
import { captureVoiceAnswer, hasGuideSpeechIntent } from "@/services/speech";

const SCORE_KEY = "little-learning-sentence-coach-score";

function cleanSentence(value: string) {
  return value.toLowerCase().replace(/[^a-z\s]/g, " ").replace(/\s+/g, " ").trim();
}

export default function SentenceCoachPage() {
  const [lessonIndex, setLessonIndex] = useState(0);
  const [wordIndex, setWordIndex] = useState(0);
  const [phase, setPhase] = useState<"words" | "sentence">("words");
  const [score, setScore] = useState(0);
  const [busy, setBusy] = useState(true);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [feedback, setFeedback] = useState("");
  const { state, effect, isSpeaking, setAvatar, speakMessageAsync, stopSpeaking } = useAvatar();

  const lesson = sentenceLessons[lessonIndex % sentenceLessons.length];
  const currentWord = lesson.words[wordIndex] ?? lesson.words[0];
  const letters = useMemo(() => spellSentenceWord(currentWord.text), [currentWord.text]);
  const spelling = letters.join(", ");

  useEffect(() => {
    const storedScore = Number(window.localStorage.getItem(SCORE_KEY));
    if (Number.isFinite(storedScore) && storedScore > 0) setScore(storedScore);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setPhase("words");
    setWordIndex(0);
    setTranscript("");
    setTypedAnswer("");
    setFeedback("");
    setBusy(true);
    const firstWord = lesson.words[0];
    const firstSpelling = spellSentenceWord(firstWord.text).join(", ");
    const introduction = `${lesson.sentence} It means: ${lesson.spokenHindi} We will read every word. First word: ${firstWord.text}. ${firstSpelling}.`;
    setAvatar({ state: "storytelling", message: introduction, speak: false, animationEffect: "story_transition", durationMs: null });
    speakMessageAsync(introduction).then(() => {
      if (cancelled) return;
      setBusy(false);
      setAvatar({ state: "happy", message: `This word is ${firstWord.text}. Tap next word when you are ready.`, speak: false, animationEffect: "none", durationMs: null });
    });
    return () => {
      cancelled = true;
      stopSpeaking();
    };
  }, [lesson.id, lesson.sentence, lesson.spokenHindi, lesson.words, setAvatar, speakMessageAsync, stopSpeaking]);

  async function teachWord(nextIndex: number) {
    if (busy || listening) return;
    const nextWord = lesson.words[nextIndex];
    const nextSpelling = spellSentenceWord(nextWord.text).join(", ");
    setWordIndex(nextIndex);
    setBusy(true);
    setFeedback("");
    const message = `${nextWord.text} means ${nextWord.hindi}. Spell ${nextWord.text}: ${nextSpelling}. Read ${nextWord.text}.`;
    setAvatar({ state: "speaking", message, speak: false, animationEffect: "pulse", durationMs: null });
    await speakMessageAsync(message);
    setBusy(false);
    setAvatar({ state: "happy", message: `This word is ${nextWord.text}.`, speak: false, animationEffect: "none", durationMs: null });
  }

  async function nextWord() {
    if (wordIndex + 1 < lesson.words.length) {
      await teachWord(wordIndex + 1);
      return;
    }
    await joinSentence();
  }

  async function joinSentence() {
    if (busy || listening) return;
    setPhase("sentence");
    setBusy(true);
    setFeedback("");
    const message = `Now join the words: ${lesson.sentence} Listen once, then read the whole sentence.`;
    setAvatar({ state: "storytelling", message, speak: false, animationEffect: "story_transition", durationMs: null });
    await speakMessageAsync(message);
    setBusy(false);
    setAvatar({ state: "listening", message: "Your turn. Read the full sentence.", speak: false, animationEffect: "none", durationMs: null });
  }

  async function replayCurrent() {
    if (busy || listening) return;
    if (phase === "sentence") {
      await joinSentence();
      return;
    }
    await teachWord(wordIndex);
  }

  async function checkSentence(rawAnswer: string, matchedCandidate = false) {
    const heard = rawAnswer.trim();
    if (!heard) {
      const message = "I could not hear the sentence. Please try again.";
      setFeedback(message);
      setAvatar({ state: "encouraging", message, speak: true, animationEffect: "gentle_hint", durationMs: null });
      return;
    }
    setTranscript(heard);

    if (hasGuideSpeechIntent(heard)) {
      const help = `Read this sentence: ${lesson.sentence}`;
      setFeedback(help);
      setAvatar({ state: "speaking", message: help, speak: false, animationEffect: "pulse", durationMs: null });
      await speakMessageAsync(help);
      return;
    }

    const correct = matchedCandidate || cleanSentence(heard) === cleanSentence(lesson.sentence);
    if (!correct) {
      const retry = `Good try. Listen: ${lesson.sentence} Now read it with me.`;
      setFeedback(`I heard “${heard}”. Try the full sentence again.`);
      setAvatar({ state: "encouraging", message: retry, speak: false, animationEffect: "gentle_hint", durationMs: null });
      await speakMessageAsync(retry);
      return;
    }

    const nextScore = score + 10;
    setScore(nextScore);
    window.localStorage.setItem(SCORE_KEY, String(nextScore));
    const success = "Wonderful reading! Ten points. Here is a new sentence.";
    setFeedback(success);
    setAvatar({ state: "celebrating", message: success, speak: false, animationEffect: "star_burst", durationMs: null });
    await speakMessageAsync(success);
    setWordIndex(0);
    setPhase("words");
    setLessonIndex((current) => (current + 1) % sentenceLessons.length);
  }

  async function startListening() {
    if (busy || listening || phase !== "sentence") return;
    stopSpeaking();
    setBusy(true);
    setListening(true);
    setTranscript("");
    setFeedback("");
    setAvatar({ state: "listening", message: "I am listening...", speak: false, animationEffect: "pulse", durationMs: null });
    try {
      const result = await captureVoiceAnswer({
        sessionId: "sentence-coach",
        activityId: `sentence-${lesson.id}`,
        answerType: "repeat_sentence",
        correctAnswer: lesson.sentence,
        acceptedAnswers: [lesson.sentence],
        timeoutMs: 10000
      });
      await checkSentence(result.raw_transcript, Boolean(result.matched_candidate));
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
    if (!typedAnswer.trim() || busy || listening || phase !== "sentence") return;
    setBusy(true);
    try {
      await checkSentence(typedAnswer);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="AI Sentence Coach">
      <section className="surface-panel mx-auto grid w-full max-w-6xl gap-5 rounded-[2rem] p-5 sm:p-7">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-ink/10 pb-5">
          <div>
            <p className="text-sm font-black uppercase text-sky">Read word by word</p>
            <h1 className="text-4xl font-black text-ink sm:text-5xl">AI Sentence Coach</h1>
          </div>
          <div className="rounded-2xl bg-sunshine px-6 py-4 text-center shadow-soft" aria-live="polite">
            <p className="text-sm font-black uppercase text-ink/60">Score</p>
            <p className="text-4xl font-black text-ink">{score}</p>
          </div>
        </header>

        <div className="grid items-center gap-5 lg:grid-cols-[12rem_1fr]">
          <div className="grid justify-items-center gap-2">
            <div className="h-40 w-40"><AIAvatar state={state} effect={effect} isSpeaking={isSpeaking} /></div>
            <span className="text-6xl" aria-hidden="true">{lesson.emoji}</span>
          </div>
          <div className="grid min-w-0 gap-3 text-center lg:text-left">
            <p className="text-3xl font-black leading-tight text-ink sm:text-5xl">{lesson.sentence}</p>
            <p className="text-2xl font-black text-berry" lang="hi">{lesson.hindi}</p>
            <p className="text-lg font-bold text-ink/65">{lesson.explanation}</p>
          </div>
        </div>

        <div className="flex flex-wrap justify-center gap-2" aria-label="Sentence words">
          {lesson.words.map((word, index) => (
            <button
              key={`${word.text}-${index}`}
              type="button"
              disabled={busy || listening}
              onClick={() => void teachWord(index)}
              className={`pressable min-h-14 rounded-lg px-5 py-3 text-xl font-black shadow-soft disabled:opacity-60 ${phase === "words" && index === wordIndex ? "bg-sky text-white" : "bg-[#f7fbff] text-ink"}`}
            >
              {word.text}
            </button>
          ))}
        </div>

        {phase === "words" ? (
          <div className="grid gap-5 border-y border-ink/10 py-5 text-center">
            <div>
              <p className="text-5xl font-black text-ink">{currentWord.text}</p>
              <p className="mt-2 text-2xl font-black text-leaf" lang="hi">{currentWord.hindi}</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2" aria-label={`Spelling: ${spelling}`}>
              {letters.map((letter, index) => (
                <span key={`${letter}-${index}`} className="grid h-14 w-12 place-items-center rounded-lg bg-white text-2xl font-black text-sky shadow-soft">{letter}</span>
              ))}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <button type="button" onClick={replayCurrent} disabled={busy || listening} className="pressable min-h-16 rounded-2xl bg-sky px-6 py-4 text-lg font-black text-white shadow-soft disabled:opacity-60">
                <span aria-hidden="true">🔊</span> Repeat word
              </button>
              <button type="button" onClick={nextWord} disabled={busy || listening} className="pressable min-h-16 rounded-2xl bg-leaf px-6 py-4 text-lg font-black text-white shadow-soft disabled:opacity-60">
                {wordIndex + 1 < lesson.words.length ? "Next word →" : "Join sentence →"}
              </button>
            </div>
          </div>
        ) : (
          <div className="grid gap-4 border-y border-ink/10 py-5 text-center">
            <p className="text-sm font-black uppercase text-leaf">Now read it together</p>
            <p className="text-3xl font-black text-ink sm:text-4xl">{lesson.sentence}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <button type="button" onClick={startListening} disabled={busy || listening} className="pressable grid min-h-24 place-items-center rounded-2xl bg-leaf px-7 py-4 text-xl font-black text-white shadow-soft disabled:opacity-60">
                <span className="text-3xl" aria-hidden="true">🎤</span>
                {listening ? "Listening..." : "Read the sentence"}
              </button>
              <button type="button" onClick={replayCurrent} disabled={busy || listening} className="pressable min-h-16 rounded-2xl bg-sky px-6 py-4 text-lg font-black text-white shadow-soft disabled:opacity-60">
                <span aria-hidden="true">🔊</span> Repeat sentence
              </button>
            </div>
          </div>
        )}

        <div className="grid gap-3">
          {transcript ? <p className="text-center text-lg font-bold text-ink/70">I heard: <strong className="text-ink">{transcript}</strong></p> : null}
          {feedback ? <p className="rounded-2xl bg-[#eef8f2] px-5 py-4 text-center text-lg font-black text-ink" aria-live="polite">{feedback}</p> : null}
          {phase === "sentence" ? (
            <form onSubmit={submitTypedAnswer} className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <input value={typedAnswer} onChange={(event) => setTypedAnswer(event.target.value)} disabled={busy || listening} className="min-h-14 min-w-0 rounded-2xl border-2 border-leaf/20 bg-white px-5 py-3 text-lg font-bold text-ink outline-none focus:border-sky" placeholder="Type the full sentence" aria-label="Type the full sentence" />
              <button type="submit" disabled={busy || listening || !typedAnswer.trim()} className="pressable min-h-14 rounded-2xl bg-ink px-7 py-3 text-lg font-black text-white disabled:opacity-50">Check</button>
            </form>
          ) : null}
        </div>
      </section>
    </AppShell>
  );
}
