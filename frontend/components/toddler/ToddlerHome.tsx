"use client";

import type { ToddlerModule, ToddlerModuleSummary } from "@/types";

export function ToddlerHome({
  stars,
  modules,
  onStart
}: {
  stars: number;
  modules: ToddlerModuleSummary[];
  onStart: (module: ToddlerModule) => void;
}) {
  return (
    <section>
      <div className="world-entrance grid min-h-[calc(100vh-2.5rem)] content-center gap-8 p-5 sm:p-7">
        <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
          <div className="grid gap-2">
            <p className="text-xl font-black text-leaf">👋 Hi little explorer!</p>
            <h1 className="text-5xl font-black text-ink sm:text-6xl">Pick one</h1>
            <p className="text-2xl font-black text-ink/70">Tap a big picture</p>
          </div>
          <span className="rounded-full bg-sunshine px-5 py-4 text-2xl font-black text-ink shadow-soft">⭐ {stars}</span>
        </div>
        <div className="relative z-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {modules.map((module) => (
            <button
              key={module.module}
              data-guide-id={`toddler-module-${module.module}`}
              type="button"
              onClick={() => onStart(module.module)}
              className="pressable adventure-card grid min-h-64 content-center justify-items-center gap-4 bg-white/90 p-5 text-center focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-sky"
              aria-label={`Learn ${module.title}`}
            >
              <span className="text-8xl" aria-hidden="true">{module.icon}</span>
              <span className="text-4xl font-black text-ink">{module.title}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
