"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import type { ChildProfile, ExperienceMode, Subject, Topic } from "@/types";
import { learningTargetStyle } from "@/lib/experience";
import { useTodayPlan } from "@/lib/useTodayPlan";

type Props = {
  subject: Subject;
  child: ChildProfile | null;
  mode: ExperienceMode;
};

/** Enough of a topic's contents to recognise it; the rest waits inside the topic. */
const SUBTOPIC_PREVIEW = 4;

/** How a topic is taught, shown so a grown-up knows what a topic will ask of them. */
const DELIVERY: Record<string, { icon: string; label: string }> = {
  hybrid: { icon: "🤲", label: "Screen + hands-on" },
  parent_guided: { icon: "👪", label: "With a grown-up" }
};

type NodeState = "done" | "ready" | "tomorrow" | "locked" | "coming-soon";

/** The chip under each node. Short, and the emoji carries it for a pre-reader. */
function chipFor(state: NodeState, isCurrent: boolean, score: number | undefined) {
  if (state === "coming-soon") return "🌱 Coming soon";
  if (state === "done") return `⭐ Done · ${score ?? 100}%`;
  if (state === "tomorrow") return "🌙 Waiting";
  if (state === "locked") return "🔒 Locked";
  // Not "play now" any more: the map does not start anything. The class does,
  // and it is already on this level today.
  return isCurrent ? "🎈 In class today" : "🎈 Ready";
}

function symbolFor(state: NodeState, topic: Topic) {
  if (state === "tomorrow") return "🌙";
  if (state === "locked") return "🔒";
  if (state === "coming-soon") return "🌱";
  return topic.icon;
}

/**
 * A subject's topics as a floating trail of levels — a picture of the journey,
 * and nothing to press.
 *
 * The map used to be the way into a lesson. It is not any more: the class is the
 * AI Teacher, it runs one stage per item of today's frozen plan, and finishing a
 * stage is the only thing that lights a level up here. So every node draws its
 * state and none of them is a link — a level a child could tap into would be a
 * second way to start a lesson, running beside the schedule and able to finish
 * a level the day had not reached. Tapping a node opens the level's own page,
 * which explains what it teaches and where it stands; it starts nothing either.
 *
 * This used to be a stack of rectangles, which reads as a settings list rather
 * than somewhere to play. A child recognises the shape of a game map long
 * before they can read the card: round levels strung along a rope, drifting in
 * the sky, the one they are on lit up and bobbing.
 *
 * Geometry is the reason the markup looks the way it does. Every level sits in
 * its own row and is pushed left or right by `--drift`; the rope to the next
 * level is one SVG per row, pinned from this node's centre (`--node-center`)
 * down a full row (`height: 100%`), so it lands exactly on the next node's
 * centre no matter how tall that row grew. That is what lets the open level
 * carry an extra bubble of detail without every rope below it going crooked.
 *
 * A level can also carry a **🧩 Remember** badge: the scheduler says a check-in
 * on it is due, so the class will ask about it again today with a different
 * question. It is a badge and not a state, because it says nothing about
 * whether the level may be taught - a finished level still reads as finished on
 * the morning its check-in falls due, and answering the check-in pays no star
 * and unlocks nothing.
 *
 * Only the level a child is actually on explains itself. Repeating the
 * objective, the delivery and the subtopics on all eight levels is what made
 * the old list a wall of grey text — here that detail rides on the one node the
 * child is being asked to tap, and the rest stay pictures and names.
 */
export function TopicList({ subject, child, mode }: Props) {
  const progress = child?.subject_progress?.[subject.subject_id];
  const unlocked = new Set(progress?.unlocked_topics ?? []);
  const completed = new Set(progress?.completed_topics ?? []);
  const scores = progress?.scores ?? {};
  // The day's plan decides what is playable, not just what is unlocked.
  // Finishing a level unlocks the next one; the next one is tomorrow's, and the
  // server refuses it today - so the map has to say so rather than let a child
  // tap into a refusal.
  const { plannedTopicIds, retentionTopicIds, loaded } = useTodayPlan(child);

  const stateOf = (topic: Topic): NodeState => {
    if (!topic.available) return "coming-soon";
    if (completed.has(topic.topic_id)) return "done";
    if (!unlocked.has(topic.topic_id)) return "locked";
    // Until the plan has actually loaded nothing is greyed out on a guess: a
    // slow request must not make a playable level look shut.
    if (loaded && plannedTopicIds.size > 0 && !plannedTopicIds.has(topic.topic_id)) return "tomorrow";
    return "ready";
  };

  // The one level the child is on: their bookmark when it is still playable,
  // otherwise the first level that is open and unfinished.
  const playable = subject.topics.filter((topic) => stateOf(topic) === "ready");
  const currentId =
    playable.find((topic) => topic.topic_id === progress?.current_topic_id)?.topic_id ??
    playable[0]?.topic_id ??
    null;

  return (
    <div className="topic-sky" data-testid="topic-map">
      <div className="topic-sky-decor" aria-hidden>
        <span className="topic-cloud topic-cloud-a" />
        <span className="topic-cloud topic-cloud-b" />
        <span className="topic-cloud topic-cloud-c" />
      </div>

      <ol className="topic-path">
        {subject.topics.map((topic, index) => {
          const state = stateOf(topic);
          const isCurrent = topic.topic_id === currentId;
          const delivery = DELIVERY[topic.delivery];
          // A topic may author no icons, and an older server sends no field at all.
          const icons = topic.subtopic_icons ?? [];
          const easy = topic.subtopic_easy ?? [];
          const next = subject.topics[index + 1];
          // The rope is lit as far as the child has walked: a finished level
          // hands on to the next one, and the rope into the level they are on
          // has its beads travelling towards it.
          const ropeTone = state === "done" ? "topic-rope-open" : "topic-rope-dim";
          const ropeLive = next && next.topic_id === currentId ? "topic-rope-live" : "";

          // This level is owed a retention check-in: it was taught a couple of
          // days ago and the class will ask about it again - a different
          // question about the same thing - before it teaches anything today.
          //
          // Drawn as a badge *beside* the state rather than as a state of its
          // own, because it is not one. A level being checked is still done, or
          // still waiting, or still today's; the check-in says nothing about
          // whether it may be taught, pays no star and unlocks nothing. Merging
          // it into `NodeState` would have made a finished level stop looking
          // finished on the morning its check-in came due.
          const checkIn = retentionTopicIds.has(topic.topic_id);

          const node = (
            <>
              <span className={`topic-node-symbol topic-symbol-${state}`} aria-hidden>
                {symbolFor(state, topic)}
                {state === "done" ? <span className="topic-node-star">⭐</span> : null}
              </span>
              <span className="topic-node-name">{topic.title}</span>
              <span className={`topic-node-chip topic-chip-${state}`}>
                {chipFor(state, isCurrent, scores[topic.topic_id])}
              </span>
              {checkIn ? (
                <span
                  data-testid="topic-check-in"
                  title="We will remember this one in class today"
                  className="rounded-full bg-sky/15 px-2.5 py-1 text-xs font-black uppercase tracking-wide text-sky"
                >
                  🧩 Remember
                </span>
              ) : null}
            </>
          );

          const shared = `topic-node topic-node-${state}${isCurrent ? " topic-node-now" : ""}`;

          return (
            <li
              key={topic.topic_id}
              className="topic-orbit"
              // Row geometry, read by the rope and the float delay in CSS.
              style={{ "--side": index % 2 === 0 ? -1 : 1, "--i": index } as CSSProperties}
            >
              {next ? (
                <svg
                  className={`topic-edge ${index % 2 === 0 ? "" : "topic-edge-flip"} ${ropeTone} ${ropeLive}`}
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                  aria-hidden
                  focusable="false"
                >
                  {/* Corner to corner: the box is pinned between the two node
                      centres, so the ends of this curve are the two nodes. */}
                  <path d="M 0 0 C 0 44, 100 56, 100 100" vectorEffect="non-scaling-stroke" />
                </svg>
              ) : null}

              <div className="topic-slot">
                {/* An authored level opens its own page — what it teaches and
                    where it stands. A level with nothing behind it, or one still
                    locked, has nothing to show and stays a picture. */}
                {topic.available && state !== "locked" ? (
                  <Link
                    id={index === 0 ? "topic-card" : undefined}
                    href={`/adventure/${subject.subject_id}/${topic.topic_id}`}
                    data-testid="topic-card"
                    data-topic-id={topic.topic_id}
                    data-state={state}
                    data-check-in={checkIn ? "true" : undefined}
                    data-current={isCurrent ? "true" : undefined}
                    style={learningTargetStyle(mode)}
                    className={shared}
                  >
                    {node}
                  </Link>
                ) : (
                  <div
                    data-testid="topic-card"
                    data-topic-id={topic.topic_id}
                    data-state={state}
                    data-current={isCurrent ? "true" : undefined}
                    style={learningTargetStyle(mode)}
                    className={shared}
                  >
                    {node}
                  </div>
                )}
              </div>

              {isCurrent ? (
                <div className="topic-now-bubble" data-testid="topic-now-bubble">
                  <p className="text-sm font-black uppercase tracking-wide text-leaf">
                    👉 You are here · Level {index + 1}
                  </p>
                  <p className="text-sm font-bold text-ink/50">
                    Your class teaches this one — no need to press anything.
                  </p>

                  {/* What the level is, in the plainest words we have for it.
                      The friendly line is written for the child; the objective
                      is the grown-up summary and stands in when there is none. */}
                  {topic.easy_line ? (
                    <p className="font-bold text-ink/75">{topic.easy_line}</p>
                  ) : topic.objective ? (
                    <p className="font-bold text-ink/70">{topic.objective}</p>
                  ) : null}

                  {icons.length ? (
                    <ul className="grid gap-1.5">
                      {topic.subtopics.slice(0, SUBTOPIC_PREVIEW).map((subtopic, position) => (
                        <li
                          key={subtopic}
                          className="flex items-start gap-2 rounded-2xl bg-white/80 px-3 py-1.5 text-sm font-bold text-ink/70"
                        >
                          <span aria-hidden className="text-base leading-6">
                            {icons[position]}
                          </span>
                          <span>
                            {subtopic}
                            {easy[position] ? (
                              <span className="block font-bold text-ink/50">{easy[position]}</span>
                            ) : null}
                          </span>
                        </li>
                      ))}
                      {topic.subtopics.length > SUBTOPIC_PREVIEW ? (
                        <li className="px-3 text-sm font-black text-ink/40">
                          +{topic.subtopics.length - SUBTOPIC_PREVIEW} more
                        </li>
                      ) : null}
                    </ul>
                  ) : null}

                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full bg-white px-3 py-1 text-sm font-black text-ink/70 shadow-soft">
                      {topic.activity_count} activities · ⭐ {topic.star_reward}
                    </span>
                    {delivery ? (
                      <span className="rounded-full bg-white px-3 py-1 text-sm font-black text-ink/70 shadow-soft">
                        {delivery.icon} {delivery.label}
                      </span>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
