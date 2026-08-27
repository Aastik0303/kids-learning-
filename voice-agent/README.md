# AI Voice Agent

Talk to it, and it talks back.

```
browser microphone -> Web Speech API -> FastAPI /chat -> Groq (Llama)
                   -> FastAPI /tts   -> Edge TTS (hi-IN-SwaraNeural)
                   -> the browser plays the reply
```

No paid APIs. Groq's free tier writes the words, Microsoft Edge's free voices
speak them, and the browser does the listening.

---

## Folder structure

```
voice-agent/
├── backend/
│   ├── __init__.py        makes `uvicorn backend.main:app` work
│   ├── main.py            FastAPI app: /health /chat /tts /stt /voices, serves the page
│   ├── ai.py              Groq. get_ai_response(user_text)
│   ├── tts.py             Edge TTS. text_to_speech(text) -> MP3 bytes
│   ├── stt.py             the speech-to-text seam: browser today, Whisper tomorrow
│   ├── requirements.txt
│   ├── .env               your real key (git-ignored)
│   └── .env.example       the template
├── frontend/
│   ├── index.html         title, mic button, transcript, reply, player, spinner
│   ├── style.css
│   └── app.js             recording, the three fetches, and every error message
├── smoke_test.py          12 checks that need no API key
├── .gitignore
└── README.md
```

---

## Install and run

### Windows (PowerShell)

```powershell
cd voice-agent

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r backend\requirements.txt

copy backend\.env.example backend\.env
notepad backend\.env          # paste your Groq key

uvicorn backend.main:app --reload --port 8009
```

If PowerShell refuses to run the activate script, either allow it once with
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, or skip activation
and call the venv directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8009
```

### Windows (cmd)

```bat
cd voice-agent
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r backend\requirements.txt
copy backend\.env.example backend\.env
uvicorn backend.main:app --reload --port 8009
```

### macOS / Linux

```bash
cd voice-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
uvicorn backend.main:app --reload --port 8009
```

### The port

The app listens on **8009**. (Saksham IQ owns 8008; this standalone demo
stays out of its way.) Two ways to say so, and they read the port from
different places:

```powershell
# uvicorn reads its own flag, not .env - so the port goes on the command line
uvicorn backend.main:app --reload --port 8009

# or let the app start itself, which reads PORT from backend/.env
python -m backend.main
```

Change `PORT` in `backend/.env` (and the `--port` flag) to move it.

### Then

Open **http://127.0.0.1:8009** in **Chrome or Edge**, click the microphone, allow
the permission prompt, and talk.

Open the page from the server, not by double-clicking `index.html`. A page opened
off the disk has a `file://` origin and the browser blocks its requests to
`127.0.0.1:8009`. FastAPI serves the frontend for exactly this reason.

Get a free Groq key at <https://console.groq.com/keys>.

---

## The API

| Method | Path       | In                                     | Out                          |
| ------ | ---------- | -------------------------------------- | ---------------------------- |
| GET    | `/health`  | –                                      | `{status, groq_key_configured, model, tts_voice, stt_engine}` |
| POST   | `/chat`    | `{"message": "user message"}`          | `{"response": "AI response"}` |
| POST   | `/tts`     | `{"text": "text to speak"}`            | `audio/mpeg` (MP3 bytes)     |
| POST   | `/stt`     | multipart `file=@clip.webm`            | `{"transcript": "...", "engine": "..."}` |
| GET    | `/voices`  | `?prefix=hi-IN`                        | every Edge voice             |

Interactive docs: <http://127.0.0.1:8009/docs>

Quick check from a second terminal:

```powershell
curl http://127.0.0.1:8009/health

curl -X POST http://127.0.0.1:8009/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"who are you\"}"

curl -X POST http://127.0.0.1:8009/tts ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Hello, how are you today\"}" --output reply.mp3
```

---

## Checking it works, without a key

```powershell
.\.venv\Scripts\python.exe smoke_test.py
```

Twelve checks, none of which cost anything: the page and its assets are served,
`/health` answers, empty and missing input are refused, a missing key produces a
readable sentence, `/stt` explains the browser engine, markdown and emoji are
stripped before speaking, and Edge TTS really does return a playable MP3. With a
key in `.env` it also makes one real Groq call.

Expected output ends with `12/12 checks passed`.

---

## Configuration

Everything lives in `backend/.env`; only the first line is required.

| Variable          | Default                   | What it does                              |
| ----------------- | ------------------------- | ----------------------------------------- |
| `GROQ_API_KEY`    | –                         | **Required.** Your Groq key.              |
| `GROQ_MODEL`      | `llama-3.3-70b-versatile` | Which model answers.                      |
| `GROQ_MAX_TOKENS` | `300`                     | Ceiling on reply length. It gets read out loud. |
| `TTS_VOICE`       | `hi-IN-SwaraNeural`       | The voice. `edge-tts --list-voices` for more. |
| `TTS_RATE`        | `+0%`                     | Speaking speed, e.g. `-10%`.              |
| `STT_ENGINE`      | `browser`                 | `browser` or `whisper`.                   |
| `WHISPER_MODEL`   | `base`                    | Which Whisper size, when `STT_ENGINE=whisper`. |

**A note on the voice.** `hi-IN-SwaraNeural` is a female Hindi voice. It reads
English text too, in an Indian accent, so it works whichever language the
assistant replies in. If you want a native English voice, set
`TTS_VOICE=en-US-AriaNeural` or `en-IN-NeerjaNeural`.

---

## What is handled when it goes wrong

| Failure                    | What happens                                                        |
| -------------------------- | ------------------------------------------------------------------- |
| Microphone permission denied | "Allow it in your browser's address bar (the padlock icon)"        |
| Nothing said / silence     | "I did not hear anything. Please try again and speak clearly."       |
| No microphone attached     | "No microphone was found."                                           |
| Browser has no Web Speech API | The mic is disabled up front and the typing box takes over.       |
| Missing / wrong Groq key   | Said on the status line at page load, before you bother speaking.    |
| Groq down, rate-limited, bad model | 502 with the specific reason, shown in the error box.        |
| Edge TTS fails or times out | The reply text still appears; only the audio is missing.            |
| Network down              | "Cannot reach the server. Is it still running at …?"                  |
| Empty or oversized input  | 422 from Pydantic, with the reason shown.                            |
| Anything unforeseen       | Logged in full server-side, one polite sentence client-side.          |

---

## Upgrading to Whisper, and then to streaming

Version one is deliberately the simple, reliable shape: record, wait, answer,
speak. Here is the path from there.

### Step 1 — Whisper instead of the browser

The seam already exists. `backend/stt.py` defines a `SpeechToText` protocol with
two implementations, and `POST /stt` calls whichever `STT_ENGINE` names.

```powershell
pip install faster-whisper
```

Then in `backend/.env`:

```
STT_ENGINE=whisper
WHISPER_MODEL=base
```

Restart. `POST /stt` now transcribes uploaded audio locally — no key, no network,
no per-minute cost. The model loads on the first request (a few seconds, once)
and transcription runs in a worker thread so it never blocks the event loop.

**No other backend file changes.** What does change is the frontend, which has to
send audio instead of text. Replace the `SpeechRecognition` block in `app.js` with
`MediaRecorder`:

```js
async function recordClip() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
  const chunks = [];
  recorder.ondataavailable = (event) => chunks.push(event.data);

  return new Promise((resolve) => {
    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      const form = new FormData();
      form.append("file", new Blob(chunks, { type: "audio/webm" }), "clip.webm");
      const response = await fetch("/stt", { method: "POST", body: form });
      if (!response.ok) throw new Error(await errorFrom(response));
      resolve((await response.json()).transcript);
    };
    recorder.start();
    // stop on the second click, or after a silence timer
    window.stopClip = () => recorder.stop();
  });
}
```

The rest of the pipeline — `handle(transcript)` — is untouched.

Why bother: Whisper is far better than the Web Speech API on accents, background
noise and Hindi, it works in Firefox and offline, and nothing is sent to Google.
The cost is a few hundred megabytes of dependency and roughly half a second of
CPU per utterance on `base`.

### Step 2 — one round trip instead of two

Right now the page calls `/chat` and then `/tts`. Collapse them into a single
`POST /talk` that returns the audio with the text in a header:

```python
@app.post("/talk")
async def talk(payload: ChatRequest) -> Response:
    reply = await ai.get_ai_response(payload.message)
    audio = await tts.text_to_speech(reply)
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"X-Reply-Text": quote(reply)},  # quote() - headers are latin-1
    )
```

One request instead of two removes a whole network round trip from the wait.

### Step 3 — stream the audio as it is made

The biggest win, and the one that makes it feel like a conversation. Today the
server waits for Groq to finish the whole sentence, then waits for Edge to
synthesise all of it, then sends it. Instead, stream Groq token by token, cut the
stream at sentence boundaries, and send each sentence's audio the moment it
exists:

```python
from fastapi.responses import StreamingResponse

async def _spoken_stream(message: str):
    buffer = ""
    stream = await ai_client.chat.completions.create(..., stream=True)
    async for chunk in stream:
        buffer += chunk.choices[0].delta.content or ""
        # Speak each sentence as soon as it is complete.
        while (cut := _sentence_end(buffer)) is not None:
            sentence, buffer = buffer[:cut + 1], buffer[cut + 1:]
            yield await tts.text_to_speech(sentence)
    if buffer.strip():
        yield await tts.text_to_speech(buffer)

@app.post("/talk/stream")
async def talk_stream(payload: ChatRequest):
    return StreamingResponse(_spoken_stream(payload.message), media_type="audio/mpeg")
```

On the client, feed it into a `MediaSource` (or play sequential blobs from a
queue) so playback starts on the first sentence. Time-to-first-word drops from
"the whole answer" to "the first sentence" — usually under a second.

### Step 4 — the finished shape

```
browser mic (MediaRecorder, voice-activity detection)
   -> WebSocket
   -> faster-whisper, streaming partial transcripts
   -> Groq, streaming tokens
   -> Edge TTS, per sentence
   -> audio streamed back over the same socket
   -> played as it arrives, and interruptible when the user starts talking again
```

A WebSocket replaces the request/response pairs, which is what lets the user cut
the assistant off mid-sentence — the thing that most makes it feel like talking
to someone rather than querying a service.

Do these in order. Each step works on its own, and each one is testable before
the next.
