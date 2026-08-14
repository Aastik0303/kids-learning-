import { isEnabled } from "@/config/featureFlags";
import { env } from "@/config/env";

/**
 * Analytics integration point (spec section 20). Deliberately a no-op sink
 * with a typed surface — a real provider (Amplitude, PostHog, Firebase)
 * drops into `configureAnalytics` without touching a single call site.
 *
 * Nothing here may carry child PII. Events reference child_id (an opaque
 * prototype id) and never a name, age or spoken transcript.
 */

export type AnalyticsEvent =
  | { name: "app_opened"; props: { cold_start: boolean } }
  | { name: "guest_home_viewed"; props: Record<string, never> }
  | { name: "feature_card_tapped"; props: { feature: string; authenticated: boolean } }
  | { name: "auth_completed"; props: { method: "login" | "register" } }
  | { name: "child_profile_created"; props: { age_group: string; mode: string } }
  | { name: "lesson_started"; props: { path_id: string; stage: number; mode: string } }
  | { name: "activity_shown"; props: { activity_kind: string; path_id: string } }
  | { name: "answer_submitted"; props: { activity_kind: string; input: string; correct: boolean } }
  | { name: "lesson_completed"; props: { path_id: string; stage: number; stars: number } }
  | { name: "hand_raised"; props: { screen: string; activity_kind: string | null } }
  | { name: "guide_action_executed"; props: { action: string; target: string | null } }
  | { name: "guide_action_rejected"; props: { reason: string; action: string } }
  | { name: "voice_capture"; props: { outcome: string; confidence: number } }
  | { name: "network_error"; props: { kind: string; path: string } };

type Sink = (name: string, props: Record<string, unknown>) => void;

let sink: Sink | null = null;
let context: Record<string, unknown> = { app_version: env.appVersion };

export function configureAnalytics(nextSink: Sink): void {
  sink = nextSink;
}

export function setAnalyticsContext(next: Record<string, unknown>): void {
  context = { ...context, ...next };
}

export function track<E extends AnalyticsEvent>(name: E["name"], props: E["props"]): void {
  if (!isEnabled("analytics")) return;

  if (sink) {
    sink(name, { ...context, ...props });
    return;
  }

  if (env.isDev) {
    console.log(`[analytics] ${name}`, props);
  }
}
