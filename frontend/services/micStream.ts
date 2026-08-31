"use client";

/**
 * The microphone, kept warm, and what it can hear.
 *
 * Two problems this solves, both of which look to a child like "the mic does
 * not work":
 *
 * 1. **It opens slowly.** The first `SpeechRecognition.start()` after a page
 *    loads has to wake the audio device and, the very first time, wait for the
 *    permission prompt. That is most of a second in which a child has already
 *    said the answer and been missed. Holding one `getUserMedia` stream open for
 *    as long as the class is on screen keeps the device awake, so the recogniser
 *    starts on the same tick the button is tapped.
 * 2. **It does not hear a quiet child.** The recogniser endpoints on its own
 *    idea of loudness and reports `no-speech`; it will not tell us that a small
 *    voice was there at all. An `AnalyserNode` on our own stream will: it reads
 *    the raw level, at a floor far below anything a recogniser calls speech, so
 *    the class can hold the microphone open while a child is still talking
 *    softly and can restart a recogniser that gave up on them.
 *
 * The stream is asked for with `autoGainControl` on, which is the part that
 * makes a whisper usable, and `noiseSuppression` off - suppression is tuned for
 * continuous background noise and it eats the short, breathy start of a
 * four-year-old saying a single letter.
 */

type MicState = {
  stream: MediaStream;
  context: AudioContext;
  analyser: AnalyserNode;
  buffer: Uint8Array;
};

let warm: MicState | null = null;
let opening: Promise<MicState | null> | null = null;

/**
 * Below this the room is quiet; above it somebody is talking, however softly.
 *
 * Deliberately far below what a speech recogniser calls speech. The whole
 * reason this meter exists is to know that a child spoke when Chrome says
 * nobody did, so it has to hear things Chrome does not. Two consecutive frames
 * are required before it counts, which is what keeps a chair scrape or a door
 * from registering as a voice.
 */
export const SPEECH_LEVEL = 0.02;

/** Frames above `SPEECH_LEVEL` before it counts as a voice rather than a knock. */
const VOICE_FRAMES = 2;

/**
 * "They are still talking", which is a louder question than "was anyone there".
 *
 * Two different bars on purpose. The sensitive one decides whether a quiet
 * child spoke at all; this one decides whether to keep a child waiting. If
 * holding the microphone open used the sensitive bar, a room with a fan in it
 * would never settle and every answer would sit there until the window ran out.
 */
const STILL_TALKING_LEVEL = 0.05;

type AudioContextConstructor = new () => AudioContext;

function audioContextConstructor(): AudioContextConstructor | null {
  if (typeof window === "undefined") return null;
  const scoped = window as Window & { webkitAudioContext?: AudioContextConstructor };
  return window.AudioContext ?? scoped.webkitAudioContext ?? null;
}

export function canUseMicrophoneLevel() {
  return (
    typeof window !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia) &&
    Boolean(audioContextConstructor())
  );
}

/**
 * Open the microphone, or hand back the one that is already open.
 *
 * Never throws: a refused or missing microphone is an outcome the caller
 * carries on without, because the recogniser has its own capture and may still
 * work. Concurrent callers share one in-flight request.
 */
export function primeMicrophone(): Promise<MicState | null> {
  if (warm && warm.stream.getAudioTracks().some((track) => track.readyState === "live")) {
    return Promise.resolve(warm);
  }
  warm = null;
  if (opening) return opening;
  if (!canUseMicrophoneLevel()) return Promise.resolve(null);

  const Context = audioContextConstructor();
  opening = navigator.mediaDevices
    .getUserMedia({
      audio: {
        echoCancellation: true,
        // Off on purpose. See the note at the top of this file.
        noiseSuppression: false,
        autoGainControl: true
      }
    })
    .then((stream) => {
      if (!Context) {
        stream.getTracks().forEach((track) => track.stop());
        return null;
      }
      const context = new Context();
      const analyser = context.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.4;
      context.createMediaStreamSource(stream).connect(analyser);
      warm = {
        stream,
        context,
        analyser,
        buffer: new Uint8Array(analyser.fftSize)
      };
      return warm;
    })
    .catch(() => null)
    .finally(() => {
      opening = null;
    });
  return opening;
}

/** Close the microphone. Called when the class leaves the screen. */
export function releaseMicrophone() {
  const open = warm;
  warm = null;
  if (!open) return;
  open.stream.getTracks().forEach((track) => track.stop());
  void open.context.close().catch(() => undefined);
}

export type VoiceActivity = {
  /** 0…1, the loudest thing in the room right now. */
  level: () => number;
  /** When somebody was last audible, or 0 if nobody has been. */
  lastVoiceAt: () => number;
  /** Whether any voice at all has been heard since listening started. */
  heardVoice: () => boolean;
  /** Whether somebody is talking at this moment. */
  speaking: () => boolean;
  stop: () => void;
};

const SILENT: VoiceActivity = {
  level: () => 0,
  lastVoiceAt: () => 0,
  heardVoice: () => false,
  speaking: () => false,
  stop: () => undefined
};

/**
 * Watch the level for as long as the microphone is open.
 *
 * `onLevel` is for the meter on screen - a child who can see the app react to
 * their voice stops shouting at it. Polled rather than run off
 * `requestAnimationFrame` so it keeps reading when the tab is not painting.
 */
export function watchVoiceActivity(onLevel?: (level: number) => void): VoiceActivity {
  const open = warm;
  if (!open) return SILENT;

  let level = 0;
  let lastVoiceAt = 0;
  let heard = false;
  let loudFrames = 0;

  const timer = window.setInterval(() => {
    open.analyser.getByteTimeDomainData(open.buffer);
    let peak = 0;
    for (let index = 0; index < open.buffer.length; index += 1) {
      peak = Math.max(peak, Math.abs((open.buffer[index] - 128) / 128));
    }
    level = peak;
    if (peak >= SPEECH_LEVEL) {
      loudFrames += 1;
      if (loudFrames >= VOICE_FRAMES) {
        heard = true;
        lastVoiceAt = Date.now();
      }
    } else {
      loudFrames = 0;
    }
    onLevel?.(peak);
  }, 50);

  return {
    level: () => level,
    lastVoiceAt: () => lastVoiceAt,
    heardVoice: () => heard,
    speaking: () => level >= STILL_TALKING_LEVEL && Date.now() - lastVoiceAt < 250,
    stop: () => {
      window.clearInterval(timer);
      onLevel?.(0);
    }
  };
}


/**
 * Keep a copy of what the microphone hears, in case the recogniser wastes it.
 *
 * The browser's recogniser and this recorder run on the same warm stream at the
 * same time, which costs nothing extra: the device is already open. Almost
 * always the recogniser answers first and the clip is thrown away unheard. The
 * clip only matters in the one case the recogniser is bad at - a child too
 * quiet for it - where it is the difference between a second attempt on the
 * server and telling a child who spoke that they said nothing.
 */
export type Recording = {
  /** Stop, and hand back what was recorded. `null` if nothing usable was. */
  stop: () => Promise<Blob | null>;
};

/** The container this browser will actually record in, or `""` for its default. */
function recordingMimeType(): string {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type)) ?? "";
}

export function startRecording(): Recording | null {
  if (!warm || typeof MediaRecorder === "undefined") return null;

  let recorder: MediaRecorder;
  try {
    const mimeType = recordingMimeType();
    recorder = new MediaRecorder(warm.stream, mimeType ? { mimeType } : undefined);
    recorder.start();
  } catch {
    return null;
  }

  const chunks: Blob[] = [];
  recorder.ondataavailable = (event) => {
    if (event.data?.size) chunks.push(event.data);
  };

  return {
    stop: () =>
      new Promise<Blob | null>((resolve) => {
        if (recorder.state === "inactive") {
          resolve(chunks.length ? new Blob(chunks, { type: recorder.mimeType }) : null);
          return;
        }
        recorder.onstop = () =>
          resolve(chunks.length ? new Blob(chunks, { type: recorder.mimeType }) : null);
        try {
          recorder.stop();
        } catch {
          resolve(null);
        }
      })
  };
}
