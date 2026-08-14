/**
 * Feature flags (spec section 20). Local and statically typed for now —
 * the getter indirection is what lets a remote config source drop in later
 * without touching call sites.
 */

export type FeatureFlag =
  | "voiceInput"
  | "voiceOutput"
  | "elevenLabsVoice"
  | "handRaise"
  | "tracing"
  | "freeDraw"
  | "stories"
  | "wordBuilding"
  | "guideVisualActions"
  | "offlineCache"
  | "analytics"
  | "parentDashboard";

const defaults: Record<FeatureFlag, boolean> = {
  voiceInput: true,
  voiceOutput: true,
  /**
   * Off by default: POST /speech/synthesize returns 503 unless the backend
   * has an ElevenLabs key configured. Device TTS is the reliable path.
   */
  elevenLabsVoice: false,
  handRaise: true,
  tracing: true,
  freeDraw: true,
  stories: true,
  wordBuilding: true,
  guideVisualActions: true,
  offlineCache: true,
  analytics: true,
  parentDashboard: true,
};

const overrides: Partial<Record<FeatureFlag, boolean>> = {};

export function isEnabled(flag: FeatureFlag): boolean {
  return overrides[flag] ?? defaults[flag];
}

/** Dev/QA affordance — also the seam a remote config provider would use. */
export function setFlag(flag: FeatureFlag, value: boolean): void {
  overrides[flag] = value;
}

export function allFlags(): Record<FeatureFlag, boolean> {
  return { ...defaults, ...overrides };
}
