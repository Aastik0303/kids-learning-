"use client";

import type { GuideResponse } from "@/types";

export type VisualGuideAction = GuideResponse["visual_action"] | null | undefined;

export function visualGuideClass(visualAction: VisualGuideAction, visualId: string) {
  if (!visualAction || visualAction.type === "none" || !visualAction.targets.includes(visualId)) return "";
  if (visualAction.type === "highlight_sequence") {
    const index = visualAction.targets.indexOf(visualId);
    return `visual-guide-highlight visual-guide-step-${Math.min(index, 4)}`;
  }
  if (visualAction.type === "pulse") return "visual-guide-pulse";
  if (visualAction.type === "trace_shape") return "visual-guide-trace";
  if (visualAction.type === "show_example") return "visual-guide-example";
  return "visual-guide-highlight";
}

export function VisualGuideRenderer({ visualAction }: { visualAction: VisualGuideAction }) {
  if (!visualAction || visualAction.type === "none" || visualAction.targets.length === 0) return null;
  return (
    <div className="sr-only" aria-live="polite">
      Visual help is showing on the question objects.
    </div>
  );
}
