"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { AppShell } from "@/components/shared/AppShell";
import { learningWorlds, linearAdventurePath, localStages, pathAccents, pathSummaries, stageTokens } from "@/data/prototype";
import { listStages } from "@/services/learning";
import { getOrCreateGuestChild } from "@/services/session";
import type { ChildProfile, Stage } from "@/types";

function StageIsland({
  stage,
  pathId,
  complete,
  current,
  unlocked,
  index
}: {
  stage: Stage;
  pathId: string;
  complete: boolean;
  current: boolean;
  unlocked: boolean;
  index: number;
}) {
  const token = stageTokens[index % stageTokens.length];
  const align = index % 2 === 0 ? "md:justify-start md:pl-[8%]" : "md:justify-end md:pr-[8%]";
  const nodeTone = complete ? "bg-leaf text-white" : current ? "bg-sunshine text-ink" : unlocked ? "bg-sky text-white" : "bg-ink/20 text-ink";
  const clickable = current;

  return (
    <div className={`stage-island relative z-10 flex ${align}`}>
      {clickable ? (
        <Link
          href={`/levels/${pathId}/${stage.stage_number}`}
          data-guide-id="current-map-level"
          className="lift-card grid w-full max-w-xl gap-4 rounded-[2rem] p-5 sm:grid-cols-[8rem_1fr] sm:items-center"
        >
          <div className="grid justify-center gap-2">
            <div className={`stage-node ${nodeTone} stage-node-current`}>
              <span className="text-3xl font-black">{stage.stage_number}</span>
            </div>
            <div className="flex justify-center gap-1">
              <span className="reward-token">{stage.star_reward}</span>
              <span className="reward-token">{token.slice(0, 1)}</span>
            </div>
          </div>
          <div>
            <p className="text-sm font-black uppercase text-leaf">Current mission</p>
            <h2 className="mt-1 text-2xl font-black text-ink">Stage {stage.stage_number}: {stage.title}</h2>
            <p className="mt-2 font-bold text-ink/70">{stage.objective}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full bg-berry/10 px-3 py-2 text-sm font-black text-berry">{stage.module_type}</span>
              <span className="rounded-full bg-sunshine/30 px-3 py-2 text-sm font-black text-ink">Reward {stage.star_reward} stars</span>
            </div>
          </div>
        </Link>
      ) : (
        <div className={`lift-card grid w-full max-w-xl gap-4 rounded-[2rem] p-5 sm:grid-cols-[8rem_1fr] sm:items-center ${!unlocked ? "opacity-60" : "opacity-75"}`}>
        <div className="grid justify-center gap-2">
          <div className={`stage-node ${nodeTone} ${current ? "stage-node-current" : ""}`}>
            <span className="text-3xl font-black">{complete ? "OK" : unlocked ? stage.stage_number : "LOCK"}</span>
          </div>
          <div className="flex justify-center gap-1">
            <span className="reward-token">{stage.star_reward}</span>
            <span className="reward-token">{token.slice(0, 1)}</span>
          </div>
        </div>
        <div>
          <p className="text-sm font-black uppercase text-leaf">{complete ? "Mission complete" : current ? "Current mission" : unlocked ? "Open mission" : "Cloud locked"}</p>
          <h2 className="mt-1 text-2xl font-black text-ink">Stage {stage.stage_number}: {stage.title}</h2>
          <p className="mt-2 font-bold text-ink/70">{stage.objective}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full bg-berry/10 px-3 py-2 text-sm font-black text-berry">{stage.module_type}</span>
            <span className="rounded-full bg-sunshine/30 px-3 py-2 text-sm font-black text-ink">Reward {stage.star_reward} stars</span>
          </div>
        </div>
        </div>
      )}
    </div>
  );
}

function pathTotal(pathId: string) {
  return pathSummaries.find((path) => path.path_id === pathId)?.total_stages ?? (pathId === "mixed_final" ? 3 : 8);
}

function pathComplete(child: ChildProfile | null, pathId: string) {
  const total = pathTotal(pathId);
  const progress = child?.path_progress[pathId];
  return Boolean(child?.completed_paths.includes(pathId)) || (progress?.completed_stages.length ?? 0) >= total;
}

function activePath(child: ChildProfile | null) {
  return linearAdventurePath.find((pathId) => !pathComplete(child, pathId)) ?? null;
}

export default function PathPage({ params }: { params: Promise<{ pathId: string }> }) {
  const { pathId } = use(params);
  const [stages, setStages] = useState<Stage[]>([]);
  const [child, setChild] = useState<ChildProfile | null>(null);

  useEffect(() => {
    setChild(getOrCreateGuestChild());
    setStages(localStages(pathId));
    listStages(pathId).then(setStages).catch(() => setStages(localStages(pathId)));
  }, [pathId]);

  const progress = child?.path_progress[pathId];
  const accent = pathAccents[pathId] ?? pathAccents.numbers;
  const world = learningWorlds[pathId] ?? learningWorlds.numbers;
  const currentPath = activePath(child);
  const pathIndex = linearAdventurePath.findIndex((item) => item === pathId);
  const previousComplete = pathIndex <= 0 || linearAdventurePath.slice(0, pathIndex).every((item) => pathComplete(child, item));
  const blocked = pathIndex !== -1 && !previousComplete;
  const percent = stages.length ? Math.round(((progress?.completed_stages.length ?? 0) / stages.length) * 100) : 0;

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className={`surface-panel rounded-[2rem] bg-gradient-to-br ${world.palette} p-5`}>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-black uppercase text-leaf">{world.decoration}</p>
              <h1 className="mt-1 text-4xl font-black leading-tight text-ink sm:text-6xl">{world.name}</h1>
              <p className="mt-3 max-w-2xl text-lg font-bold text-ink/70">{world.realm}</p>
            </div>
            <Link className="pressable rounded-full bg-white px-4 py-3 font-black text-ink shadow-soft" href="/levels">
              All Worlds
            </Link>
          </div>
          <div className="mt-5 grid gap-2">
            <div className="flex justify-between gap-3 font-black text-ink">
              <span>Adventure progress</span>
              <span>{percent}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${percent}%` }} />
            </div>
          </div>
        </div>

        {blocked ? (
          <div className="surface-panel grid justify-items-center gap-4 rounded-[2rem] p-6 text-center">
            <h2 className="text-4xl font-black text-ink">Bridge locked</h2>
            <p className="max-w-xl text-xl font-bold text-ink/70">The adventure opens one world at a time. Follow the glowing node on the map.</p>
            <Link className="pressable rounded-3xl bg-leaf px-5 py-4 text-xl font-black text-white shadow-soft" href="/levels">
              Return to Adventure
            </Link>
          </div>
        ) : null}

        <div className={`map-world ${world.sky} p-4 sm:p-7`}>
          <span className="floating-cloud left-8 top-10 opacity-80" />
          <span className="floating-cloud right-10 top-40 opacity-70" />
          <span className="balloon right-8 top-72 bg-berry" />
          <div className="map-trail" />
          <div className="relative z-10 grid gap-7 py-8">
            {stages.map((stage, index) => {
              const unlocked = progress?.unlocked_stages.includes(stage.stage_number) ?? stage.stage_number === 1;
              const complete = progress?.completed_stages.includes(stage.stage_number) ?? false;
              const current = !blocked && currentPath === pathId && unlocked && !complete;
              return (
                <StageIsland
                  key={stage.stage_id}
                  stage={stage}
                  pathId={pathId}
                  complete={complete}
                  current={current}
                  unlocked={unlocked}
                  index={index}
                />
              );
            })}
          </div>
          <div className="relative z-10 mx-auto grid max-w-xl justify-items-center gap-4 rounded-[2rem] bg-white/80 p-6 text-center shadow-soft">
            <div className="treasure-chest" />
            <h2 className="text-3xl font-black text-ink">World Treasure</h2>
            <p className="text-lg font-bold text-ink/70">Complete every mission to collect the {world.reward}.</p>
            <span className={`rounded-full px-5 py-3 font-black ${accent.soft}`}>{percent === 100 ? "Treasure collected" : "Treasure waiting"}</span>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
