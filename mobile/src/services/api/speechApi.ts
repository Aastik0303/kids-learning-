import { env } from "@/config/env";
import { apiClient } from "@/services/api/client";
import type { AnswerResolutionResult, SpeechNormalizeRequest } from "@/types/domain";

/** /speech — transcript normalisation and (optional) hosted TTS. */
export const speechApi = {
  /**
   * Turns a raw STT transcript into a resolved answer using the question's
   * own candidates. This is where "tree → three → 3" happens, and it is
   * deterministic server-side code, not an LLM call.
   */
  normalize(payload: SpeechNormalizeRequest) {
    return apiClient.post<AnswerResolutionResult>("/speech/normalize", {
      transcript: payload.transcript,
      confidence: payload.confidence,
      answer_type: payload.answer_type ?? "",
      activity_id: payload.activity_id ?? null,
      correct_answer: payload.correct_answer ?? null,
      accepted_answers: payload.accepted_answers ?? [],
      options: payload.options ?? [],
    });
  },

  /**
   * Hosted (ElevenLabs) speech. Returns 503 unless the backend has a key,
   * so callers must be prepared to fall back to device TTS — see
   * `services/audio/tts.ts`.
   */
  async synthesizeUrl(text: string): Promise<string | null> {
    try {
      const response = await fetch(`${env.apiBaseUrl}/speech/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) return null;

      // expo-audio plays from a URI, so hand back a base64 data URI.
      const buffer = await response.arrayBuffer();
      const base64 = arrayBufferToBase64(buffer);
      return `data:audio/mpeg;base64,${base64}`;
    } catch {
      return null;
    }
  },
};

const BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/**
 * Hand-rolled because Hermes does not ship `btoa`, and pulling in a
 * polyfill for one audio path is not worth the bundle.
 */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let output = "";

  for (let i = 0; i < bytes.length; i += 3) {
    const byte0 = bytes[i] ?? 0;
    const byte1 = bytes[i + 1];
    const byte2 = bytes[i + 2];

    output += BASE64_ALPHABET[byte0 >> 2];
    output += BASE64_ALPHABET[((byte0 & 0x03) << 4) | ((byte1 ?? 0) >> 4)];
    output += byte1 === undefined ? "=" : BASE64_ALPHABET[((byte1 & 0x0f) << 2) | ((byte2 ?? 0) >> 6)];
    output += byte2 === undefined ? "=" : BASE64_ALPHABET[byte2 & 0x3f];
  }

  return output;
}
