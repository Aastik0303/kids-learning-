"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { learningWorlds, linearAdventurePath, pathSummaries } from "@/data/prototype";
import type { ChildProfile, PathProgress, PathSummary } from "@/types";

type WorldId = (typeof linearAdventurePath)[number];
type NodeState = "locked" | "upcoming" | "current" | "completed";

const worldScenes: Record<
  WorldId,
  {
    eyebrow: string;
    place: string;
    pathLabel: string;
    motif: string;
    icon: string;
    stageTitles: string[];
    stageIcons: string[];
  }
> = {
  numbers: {
    eyebrow: "Apple Orchard",
    place: "Number Kingdom",
    pathLabel: "apple trail",
    motif: "orchard",
    icon: "🔢",
    stageTitles: ["Entrance", "Meet Number 1", "Learn 1 to 3", "Count Apples", "Match Numbers", "Mini Challenge", "Boss Challenge", "Reward Ceremony"],
    stageIcons: ["🗺️", "1️⃣", "🍎", "🔢", "🧩", "⭐", "🏰", "🎉"]
  },
  alphabets: {
    eyebrow: "Letter Woods",
    place: "Alphabet Forest",
    pathLabel: "leaf bridge",
    motif: "forest",
    icon: "🔠",
    stageTitles: ["Entrance", "Meet Letter A", "Listen to Sounds", "Find Letters", "Match Letters", "Mini Challenge", "Boss Challenge", "Reward Ceremony"],
    stageIcons: ["🗺️", "📖", "🔊", "🔍", "✏️", "⭐", "🏰", "🎉"]
  },
  colours: {
    eyebrow: "Rainbow Garden",
    place: "Colour Garden",
    pathLabel: "flower path",
    motif: "garden",
    icon: "🌈",
    stageTitles: ["Entrance", "Meet Red", "Mix Bright Colours", "Find Colours", "Match Paint", "Mini Challenge", "Boss Challenge", "Reward Ceremony"],
    stageIcons: ["🗺️", "🔴", "🎨", "🔍", "🌈", "⭐", "🏰", "🎉"]
  },
  shapes: {
    eyebrow: "Block Beach",
    place: "Shape Island",
    pathLabel: "island stones",
    motif: "island",
    icon: "🔺",
    stageTitles: ["Entrance", "Meet Circle", "Build Shapes", "Sort Blocks", "Match Shapes", "Mini Challenge", "Boss Challenge", "Reward Ceremony"],
    stageIcons: ["🗺️", "🔴", "🧩", "🔷", "⬜", "⭐", "🏰", "🎉"]
  },
  mixed_final: {
    eyebrow: "Treasure Hunt",
    place: "Magic Castle",
    pathLabel: "castle steps",
    motif: "castle",
    icon: "🏰",
    stageTitles: ["Castle Gate", "Treasure Games", "Boss Challenge"],
    stageIcons: ["🗝️", "💎", "🏆"]
  }
};

function completedCount(progress: PathProgress | undefined, total: number) {
  return Math.min(progress?.completed_stages.length ?? 0, total);
}

function isComplete(child: ChildProfile | null, pathId: WorldId, total: number) {
  return Boolean(child?.completed_paths.includes(pathId)) || completedCount(child?.path_progress[pathId], total) >= total;
}

function nextStage(progress: PathProgress | undefined, total: number) {
  const completed = new Set(progress?.completed_stages ?? []);
  for (let stage = 1; stage <= total; stage += 1) {
    if (!completed.has(stage)) return stage;
  }
  return total;
}

function stateLabel(state: NodeState) {
  if (state === "completed") return "Done";
  if (state === "current") return "Now";
  if (state === "upcoming") return "Next";
  return "Lock";
}

function nodeIcon(state: NodeState, icon: string) {
  if (state === "completed") return "⭐";
  if (state === "locked") return "";
  return icon;
}

function pathTotal(paths: PathSummary[], pathId: WorldId) {
  return paths.find((path) => path.path_id === pathId)?.total_stages ?? (pathId === "mixed_final" ? 3 : 8);
}

function WorldDecor({ motif }: { motif: string }) {
  return (
    <div className="world-decor" aria-hidden="true">
      <span className={`decor-piece decor-${motif}-one`} />
      <span className={`decor-piece decor-${motif}-two`} />
      <span className={`decor-piece decor-${motif}-three`} />
      <span className="map-butterfly butterfly-a" />
      <span className="map-butterfly butterfly-b" />
    </div>
  );
}

export function LearningAdventureMap({ child, paths }: { child: ChildProfile | null; paths: PathSummary[] }) {
  const currentNodeRef = useRef<HTMLAnchorElement | null>(null);
  const prefersReducedMotion = useReducedMotion();
  const summaries = paths.length ? paths : pathSummaries;

  const progressModel = useMemo(() => {
    let activePath: WorldId | null = null;
    let activeStage = 1;
    let previousComplete = true;

    for (const pathId of linearAdventurePath) {
      const total = pathTotal(summaries, pathId);
      const complete = isComplete(child, pathId, total);
      if (previousComplete && !complete && activePath === null) {
        activePath = pathId;
        activeStage = nextStage(child?.path_progress[pathId], total);
      }
      previousComplete = previousComplete && complete;
    }

    return {
      activePath,
      activeStage,
      allComplete: activePath === null && linearAdventurePath.every((pathId) => isComplete(child, pathId, pathTotal(summaries, pathId)))
    };
  }, [child, summaries]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      currentNodeRef.current?.scrollIntoView({ behavior: "auto", block: "center" });
    }, 60);
    return () => window.clearTimeout(timer);
  }, [progressModel.activePath, progressModel.activeStage]);

  return (
    <section className="adventure-map-shell" aria-label="Learning adventure map">
      <div className="adventure-map" aria-label="Sequential learning adventure map">
        <span className="map-cloud cloud-one" aria-hidden="true" />
        <span className="map-cloud cloud-two" aria-hidden="true" />
        <span className="map-cloud cloud-three" aria-hidden="true" />
        <span className="map-river" aria-hidden="true" />
        <span className="map-road" aria-hidden="true" />
        <span className="map-sparkles" aria-hidden="true" />

        <div className="start-village">
          <span className="village-house" aria-hidden="true" />
          <div>
            <p className="text-sm font-black uppercase text-leaf">Start Village</p>
            <h2 className="text-3xl font-black text-ink">Adventure begins</h2>
          </div>
        </div>

        {linearAdventurePath.map((pathId, worldIndex) => {
          const total = pathTotal(summaries, pathId);
          const world = learningWorlds[pathId];
          const scene = worldScenes[pathId];
          const previousWorldsComplete = linearAdventurePath.slice(0, worldIndex).every((previousId) =>
            isComplete(child, previousId, pathTotal(summaries, previousId))
          );
          const worldComplete = isComplete(child, pathId, total);
          const progress = child?.path_progress[pathId];
          const currentStage = progressModel.activePath === pathId ? progressModel.activeStage : nextStage(progress, total);
          const percent = Math.round((completedCount(progress, total) / total) * 100);
          const lockedWorld = !previousWorldsComplete;
          const worldState = lockedWorld ? "locked" : worldComplete ? "completed" : progressModel.activePath === pathId ? "current" : "upcoming";

          return (
            <motion.article
              key={pathId}
              className={`world-section world-${pathId} world-state-${worldState}`}
              initial={false}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: prefersReducedMotion ? 0 : 0.36, ease: [0.22, 1, 0.36, 1] }}
            >
              <WorldDecor motif={scene.motif} />
              <div className="world-header">
                <div>
                  <p className="text-sm font-black uppercase text-leaf">{scene.eyebrow}</p>
                  <h2 className="text-4xl font-black leading-tight text-ink sm:text-5xl">{scene.place}</h2>
                  <p className="mt-2 max-w-xl text-lg font-bold text-ink/70">{world.realm}</p>
                </div>
                <div className="world-reward">
                  <span>{world.reward}</span>
                  <strong>{lockedWorld ? "Locked" : worldComplete ? "Earned" : `${percent}%`}</strong>
                </div>
              </div>

              <div className="world-stage-path" aria-label={`${scene.place} ${scene.pathLabel}`}>
                {Array.from({ length: total }, (_, index) => {
                  const stageNumber = index + 1;
                  const complete = Boolean(progress?.completed_stages.includes(stageNumber)) || worldComplete;
                  const isCurrent = !lockedWorld && progressModel.activePath === pathId && currentStage === stageNumber && !complete;
                  const state: NodeState = lockedWorld ? "locked" : complete ? "completed" : isCurrent ? "current" : "upcoming";
                  const title = scene.stageTitles[index] ?? `Stage ${stageNumber}`;
                  const icon = scene.stageIcons[index] ?? scene.icon;
                  const alignClass = index % 2 === 0 ? "node-left" : "node-right";
                  const href = `/levels/${pathId}/${stageNumber}`;

                  return (
                    <div
                      key={`${pathId}-${stageNumber}`}
                      className={`map-node-row ${alignClass}`}
                    >
                      {isCurrent ? <span className="tap-arrow" aria-hidden="true" /> : null}
                      {isCurrent ? (
                        <Link
                          ref={currentNodeRef}
                          href={href}
                          data-guide-id="current-map-level"
                          className={`map-level-node node-${state} pressable`}
                          aria-label={`Current level, ${scene.place}, ${title}`}
                        >
                          <span className="node-symbol" aria-hidden="true">{icon}</span>
                          <span className="node-copy">
                            <strong>{stateLabel(state)}</strong>
                            <small>{stageNumber}. {title}</small>
                          </span>
                        </Link>
                      ) : (
                        <button className={`map-level-node node-${state}`} type="button" disabled aria-label={`${scene.place}, ${title}, ${stateLabel(state)}`}>
                          <span className="node-symbol" aria-hidden="true">{nodeIcon(state, icon)}</span>
                          <span className="node-copy">
                            <strong>{stateLabel(state)}</strong>
                            <small>{stageNumber}. {title}</small>
                          </span>
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className={`world-ceremony ${worldComplete ? "ceremony-complete" : ""}`}>
                <span className="ceremony-crown" aria-hidden="true" />
                <div>
                  <p className="text-sm font-black uppercase text-leaf">{worldComplete ? "World Complete" : lockedWorld ? "Bridge Closed" : "Reward Ahead"}</p>
                  <p className="text-2xl font-black text-ink">
                    {worldComplete ? `${scene.place} shines.` : lockedWorld ? "Complete the world above." : `${world.reward} is waiting.`}
                  </p>
                </div>
              </div>
            </motion.article>
          );
        })}

        <motion.div
          className={`graduation-castle ${progressModel.allComplete ? "graduation-ready" : ""}`}
          initial={false}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.32 }}
        >
          <span className="castle-fireworks" aria-hidden="true" />
          <div>
            <p className="text-sm font-black uppercase text-leaf">Graduation Castle</p>
            <h2 className="text-4xl font-black text-ink">Certificate Celebration</h2>
            <p className="mt-2 text-lg font-bold text-ink/70">The final reward opens after Magic Castle.</p>
          </div>
          {progressModel.allComplete ? (
            <Link className="pressable rounded-3xl bg-leaf px-6 py-4 text-xl font-black text-white shadow-soft" href="/certificate">
              Open Certificate
            </Link>
          ) : (
            <span className="rounded-3xl bg-white/70 px-6 py-4 text-xl font-black text-ink/55 shadow-soft">Locked</span>
          )}
        </motion.div>
      </div>
    </section>
  );
}
