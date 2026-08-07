"use client";

import type { ToddlerModule, ToddlerModuleSummary } from "@/types";

const levelNodes = [
  { label: "ABC", state: "current", icon: "🔤" },
  { label: "DEF", state: "next", icon: "⭐" },
  { label: "GHI", state: "locked", icon: "🔒" }
];

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
    <section className="grid gap-5">
      <div className="world-entrance grid min-h-[28rem] content-between gap-6 p-5 sm:p-7">
        <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xl font-black text-leaf">👋 Hi little explorer!</p>
            <h1 className="mt-2 text-5xl font-black text-ink sm:text-6xl">What should we learn?</h1>
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
              className="pressable adventure-card grid min-h-56 content-center justify-items-center gap-4 bg-white/80 p-5 text-center"
            >
              <span className="text-7xl" aria-hidden="true">{module.icon}</span>
              <span className="text-4xl font-black text-ink">{module.title}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="surface-panel grid gap-4 rounded-[2rem] p-5">
        <h2 className="text-3xl font-black text-ink">Learning path</h2>
        <div className="mx-auto grid w-full max-w-sm justify-items-center gap-2">
          {levelNodes.map((node, index) => (
            <div key={node.label} className="grid justify-items-center gap-2">
              <div className={`grid h-24 w-24 place-items-center rounded-full text-3xl font-black shadow-soft ${node.state === "current" ? "stage-node-current bg-leaf text-white" : node.state === "locked" ? "bg-white/70 text-ink/40" : "bg-sunshine text-ink"}`}>
                {node.icon}
              </div>
              <p className="text-xl font-black text-ink">{node.label}</p>
              {index < levelNodes.length - 1 ? <span className="h-10 w-3 rounded-full bg-sunshine" aria-hidden="true" /> : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
