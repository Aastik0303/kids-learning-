/**
 * AI Voice Assistant - the whole client.
 *
 *   click the mic -> Web Speech API listens -> transcript
 *                 -> POST /chat  (Groq writes the reply)
 *                 -> POST /tts   (Edge TTS speaks it)
 *                 -> the browser plays it
 *
 * The listening happens here, in the browser, because that is the free
 * speech-to-text that needs no install. The server has an /stt endpoint waiting
 * for the day Whisper takes over; see the README.
 *
 * Everything that can fail is caught and shown in words. A voice app that
 * silently does nothing is indistinguishable from a broken one.
 */

(() => {
  "use strict";

  // Same origin as the page, because the FastAPI app serves this file. Point it
  // at http://127.0.0.1:8000 if you ever open index.html from disk instead.
  const API = "";

  const el = {
    status: document.getElementById("status"),
    mic: document.getElementById("micButton"),
    micHint: document.getElementById("micHint"),
    language: document.getElementById("language"),
    loading: document.getElementById("loading"),
    loadingLabel: document.getElementById("loadingLabel"),
    error: document.getElementById("error"),
    userPanel: document.getElementById("userPanel"),
    userText: document.getElementById("userText"),
    aiPanel: document.getElementById("aiPanel"),
    aiText: document.getElementById("aiText"),
    player: document.getElementById("player"),
    typedForm: document.getElementById("typedForm"),
    typedInput: document.getElementById("typedInput"),
    sendButton: document.getElementById("sendButton")
  };

  let recognition = null;
  let isRecording = false;
  let isBusy = false;
  // The URL of the clip currently loaded in the player. Revoked before the next
  // one replaces it, or every reply leaks a blob for the life of the page.
  let audioUrl = null;

  // ------------------------------------------------------------------ helpers

  function showError(message) {
    el.error.textContent = message;
    el.error.hidden = false;
  }

  function clearError() {
    el.error.hidden = true;
    el.error.textContent = "";
  }

  function setLoading(on, label) {
    isBusy = on;
    el.loading.hidden = !on;
    if (label) el.loadingLabel.textContent = label;
    el.mic.disabled = on;
    el.sendButton.disabled = on;
  }

  function showUser(text) {
    el.userText.textContent = text;
    el.userPanel.hidden = false;
  }

  function showAI(text) {
    el.aiText.textContent = text;
    el.aiPanel.hidden = false;
  }

  /**
   * Read the server's error message out of a failed response.
   *
   * FastAPI puts it in `detail` - either a string we raised, or the list of
   * validation problems Pydantic produced. Both are turned into one sentence,
   * because the user is looking at a box that fits one.
   */
  async function errorFrom(response) {
    let detail = "";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail) && body.detail.length) {
        detail = body.detail.map((item) => item.msg).join("; ");
      }
    } catch {
      // Not JSON - a proxy error page, or the server died mid-answer.
    }
    return detail || `The server answered ${response.status}.`;
  }

  // --------------------------------------------------------------- the server

  /** Ask /health what is configured, so a missing key is visible before you speak. */
  async function checkHealth() {
    try {
      const response = await fetch(`${API}/health`);
      if (!response.ok) throw new Error(await errorFrom(response));
      const health = await response.json();

      if (!health.groq_key_configured) {
        el.status.textContent =
          "No GROQ_API_KEY set - put your key in backend/.env and restart the server.";
        el.status.className = "status status--warn";
        return;
      }

      el.status.textContent = `Ready · ${health.model} · voice ${health.tts_voice}`;
      el.status.className = "status status--ok";
    } catch (error) {
      el.status.textContent = `Cannot reach the server: ${error.message}`;
      el.status.className = "status status--warn";
    }
  }

  /** Send the user's words to Groq and get the reply. */
  async function askAI(message) {
    const response = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });
    if (!response.ok) throw new Error(await errorFrom(response));
    const data = await response.json();
    if (!data.response) throw new Error("The AI sent back an empty reply.");
    return data.response;
  }

  /** Turn the reply into audio and play it. */
  async function speak(text) {
    const response = await fetch(`${API}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    if (!response.ok) throw new Error(await errorFrom(response));

    const blob = await response.blob();
    if (!blob.size) throw new Error("The voice service sent back an empty clip.");

    if (audioUrl) URL.revokeObjectURL(audioUrl);
    audioUrl = URL.createObjectURL(blob);
    el.player.src = audioUrl;

    try {
      await el.player.play();
    } catch {
      // Autoplay was blocked - which should not happen, because everything here
      // starts from a click. The player has controls, so say what to do.
      showError("Tap the play button to hear the reply.");
    }
  }

  // -------------------------------------------------------------- the pipeline

  /**
   * One full turn: show what was said, ask the AI, speak the answer.
   *
   * The reply is shown before it is spoken. If Edge TTS fails, the user has
   * still had their answer - a broken speaker should not swallow the words.
   */
  async function handle(userMessage) {
    const message = (userMessage || "").trim();
    if (!message) {
      showError("I did not catch anything. Please try again.");
      return;
    }

    clearError();
    showUser(message);
    el.aiPanel.hidden = true;

    let reply;
    try {
      setLoading(true, "Thinking…");
      reply = await askAI(message);
      showAI(reply);
    } catch (error) {
      showError(networkAware(error, "Could not get an answer."));
      return;
    } finally {
      setLoading(false);
    }

    try {
      setLoading(true, "Speaking…");
      await speak(reply);
    } catch (error) {
      showError(networkAware(error, "Could not play the reply.") + " The text is above.");
    } finally {
      setLoading(false);
    }
  }

  /** `fetch` throws a bare TypeError when the network is down. Name it. */
  function networkAware(error, fallback) {
    if (error instanceof TypeError) {
      return "Cannot reach the server. Is it still running at " + (API || location.origin) + "?";
    }
    return error.message || fallback;
  }

  // ------------------------------------------------------------------ the mic

  /** Build the recogniser, or return null when this browser has none. */
  function createRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;

    const recogniser = new SpeechRecognition();
    recogniser.lang = el.language.value;
    recogniser.continuous = false; // one utterance per press
    recogniser.interimResults = true; // show the words as they arrive
    recogniser.maxAlternatives = 1;

    let finalText = "";

    recogniser.onstart = () => {
      isRecording = true;
      finalText = "";
      clearError();
      el.mic.classList.add("is-recording");
      el.mic.setAttribute("aria-label", "Stop recording");
      el.micHint.textContent = "Listening… click again to stop";
    };

    recogniser.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const chunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += chunk;
        else interim += chunk;
      }
      // Live feedback, so a long sentence does not look like a frozen page.
      showUser((finalText + interim).trim() || "…");
    };

    recogniser.onerror = (event) => {
      // `onend` still fires after this, and it does the button tidy-up.
      showError(speechErrorMessage(event.error));
    };

    recogniser.onend = () => {
      isRecording = false;
      el.mic.classList.remove("is-recording");
      el.mic.setAttribute("aria-label", "Start recording");
      el.micHint.textContent = "Click to start";

      const said = finalText.trim();
      if (said) {
        handle(said);
      } else if (el.error.hidden) {
        // Ended with nothing, and no error was reported: silence.
        showError("I did not hear anything. Please try again and speak clearly.");
      }
    };

    return recogniser;
  }

  /** The Web Speech API's error codes, in words a person can act on. */
  function speechErrorMessage(code) {
    switch (code) {
      case "not-allowed":
      case "service-not-allowed":
        return (
          "Microphone permission was denied. Allow it in your browser's address " +
          "bar (the padlock icon) and try again."
        );
      case "no-speech":
        return "I did not hear anything. Please try again and speak clearly.";
      case "audio-capture":
        return "No microphone was found. Check that one is plugged in and enabled.";
      case "network":
        return "The speech service could not be reached. Check your internet connection.";
      case "aborted":
        return "Recording stopped.";
      default:
        return `Could not record: ${code}.`;
    }
  }

  function toggleRecording() {
    if (isBusy) return;

    if (isRecording) {
      recognition.stop(); // `onend` handles the rest
      return;
    }

    // Rebuilt each time so a language change takes effect on the next press.
    recognition = createRecognition();
    if (!recognition) {
      showError("This browser cannot record. Use Chrome or Edge, or type below.");
      return;
    }

    try {
      recognition.start();
    } catch (error) {
      // Thrown when start() is called twice in a row - harmless, but say so.
      showError(`Could not start recording: ${error.message}`);
    }
  }

  // ------------------------------------------------------------------- wiring

  el.mic.addEventListener("click", toggleRecording);

  el.typedForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = el.typedInput.value.trim();
    if (!text) {
      showError("Type something first.");
      return;
    }
    el.typedInput.value = "";
    handle(text);
  });

  // A browser with no Web Speech API (Firefox, most in-app browsers) still gets a
  // working app - it just types instead of talking. Said up front rather than
  // discovered by pressing a button that does not work.
  if (!(window.SpeechRecognition || window.webkitSpeechRecognition)) {
    el.mic.disabled = true;
    el.micHint.textContent = "Voice input needs Chrome or Edge";
    showError(
      "This browser has no speech recognition. You can still type your message below."
    );
  }

  checkHealth();
})();
