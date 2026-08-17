"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { useResponsive } from "@/lib/responsive/useResponsive";

/**
 * Writing practice: the child follows a shape with a finger, and the part they
 * have covered turns green as they go.
 *
 * The guidance is the point of this component. A blank box asking a
 * two-year-old to "write A" teaches nothing, so the letter is always on screen
 * in grey, a pulsing dot marks where to start, and every stroke that lands on
 * the letter fills in green — the child can see what is left to do without
 * anyone reading them an instruction.
 *
 * Drawing is also where a child gets stuck without being able to say so, so the
 * canvas coaches:
 *   - "Watch me" walks a finger dot along the whole shape, in order, so the
 *     child sees the direction rather than only the destination.
 *   - After two strokes that go nowhere the demo plays by itself and the guide
 *     is asked for a spoken tip. Nobody has to ask for help to get it.
 *   - Every piece of coaching is spoken, because the child cannot read it.
 *
 * Accuracy is measured here on the device, from the gesture, exactly as the
 * curriculum contract requires: no model is asked whether the writing is good.
 * The AI only ever talks — it never decides that a shape is finished.
 * Coverage is how much of the shape was touched; spill is how much of the
 * child's drawing landed nowhere near it, so scribbling over the whole box does
 * not pass.
 */

const SIZE = 320; // logical canvas size, in CSS pixels
const CELL = 8; // resolution of the target mask
const REACH = 20; // how near a finger must pass for a piece to count as traced
const STROKE = 26; // how thick the child's line is drawn
const MAX_SPILL = 0.45; // beyond this, the drawing is not following the shape
const DEMO_FRAMES = 90; // roughly 1.5s for one "watch me" pass

type Point = { x: number; y: number };

const SHAPES: Record<string, (ctx: CanvasRenderingContext2D) => void> = {
  circle: (c) => c.arc(160, 160, 108, 0, Math.PI * 2),
  oval: (c) => c.ellipse(160, 160, 124, 88, 0, 0, Math.PI * 2),
  square: (c) => c.rect(56, 56, 208, 208),
  rectangle: (c) => c.rect(36, 86, 248, 148),
  triangle: (c) => {
    c.moveTo(160, 46);
    c.lineTo(280, 268);
    c.lineTo(40, 268);
    c.closePath();
  },
  line: (c) => {
    c.moveTo(44, 160);
    c.lineTo(276, 160);
  },
  curve: (c) => {
    c.moveTo(40, 192);
    c.quadraticCurveTo(160, 56, 280, 192);
  },
  zigzag: (c) => {
    c.moveTo(40, 108);
    c.lineTo(120, 216);
    c.lineTo(200, 108);
    c.lineTo(280, 216);
  },
  slant: (c) => {
    c.moveTo(62, 266);
    c.lineTo(258, 54);
  },
  stroke: (c) => {
    c.moveTo(160, 44);
    c.lineTo(160, 276);
  },
  // The pre-writing strokes, by the names the curriculum gives them. Without
  // these a "standing line" fell through to the glyph branch and the child was
  // asked to trace the letters "STA".
  standing_line: (c) => {
    c.moveTo(160, 44);
    c.lineTo(160, 276);
  },
  sleeping_line: (c) => {
    c.moveTo(44, 160);
    c.lineTo(276, 160);
  },
  left_slant: (c) => {
    c.moveTo(258, 54);
    c.lineTo(62, 266);
  },
  right_slant: (c) => {
    c.moveTo(62, 266);
    c.lineTo(258, 54);
  },
  up_curve: (c) => {
    c.moveTo(40, 208);
    c.quadraticCurveTo(160, 40, 280, 208);
  },
  down_curve: (c) => {
    c.moveTo(40, 112);
    c.quadraticCurveTo(160, 280, 280, 112);
  },
  left_curve: (c) => {
    c.moveTo(232, 68);
    c.arc(160, 160, 100, -Math.PI / 4, Math.PI / 4, true);
  },
  right_curve: (c) => {
    c.moveTo(88, 68);
    c.arc(160, 160, 100, (-3 * Math.PI) / 4, (3 * Math.PI) / 4);
  },
  loop: (c) => c.ellipse(160, 160, 96, 96, 0, 0, Math.PI * 2)
};

/** How a shape is written, said the way a nursery teacher says it. */
const STROKE_WORDS: Record<string, string> = {
  circle: "Go all the way around, like a big round ball.",
  oval: "Go around, long and thin like an egg.",
  square: "Across, down, back and up. Four straight sides.",
  rectangle: "A long line across, then down, and around.",
  triangle: "Down one side, across the bottom, then back up.",
  line: "One straight line, all the way across.",
  curve: "Up like a hill, then down the other side.",
  zigzag: "Down, up, down, up. Sharp corners.",
  slant: "A slanty line, from the bottom up to the top.",
  stroke: "Straight down, from the top to the bottom.",
  standing_line: "Start at the top and pull straight down.",
  sleeping_line: "A sleeping line goes across, left to right.",
  left_slant: "Slant down to the left.",
  right_slant: "Slant up to the right.",
  up_curve: "A smiling curve, up and over.",
  down_curve: "A curve that dips down, like a cup.",
  left_curve: "Curve around to the left.",
  right_curve: "Curve around to the right.",
  loop: "Go around and around, back to the start."
};

function strokeWords(target: string) {
  const key = target.trim().toLowerCase();
  if (STROKE_WORDS[key]) return STROKE_WORDS[key];
  return "Start on the blue dot and follow the grey shape.";
}

/**
 * Steps that ask for a drawing rather than a shape.
 *
 * The curriculum authors these as `trace_target: "free"` with no accuracy to
 * reach — the point is holding the crayon, not hitting a line. Without this the
 * name fell through to the glyph branch and a two-year-old was asked to trace
 * the letters "FRE", which nothing on earth would have let them finish.
 */
const FREE_DRAW = new Set(["free", "free_draw", "freedraw", "scribble", "doodle", "anything", "draw"]);

function isFreeDraw(target: string) {
  return FREE_DRAW.has(target.trim().toLowerCase());
}

/** Paints the shape to follow. Letters and numerals are drawn as themselves. */
function paintGuide(ctx: CanvasRenderingContext2D, target: string, colour: string) {
  const shape = SHAPES[target.trim().toLowerCase()];
  ctx.save();
  if (shape) {
    ctx.strokeStyle = colour;
    ctx.lineWidth = 20;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    shape(ctx);
    ctx.stroke();
  } else {
    // A capital is the right default: the curriculum teaches capitals first and
    // authors them as "A". "small_a" is the deliberate exception — Nursery
    // writes the small letter too, and it must be drawn as a small letter.
    const raw = target.trim();
    const small = /^small_([a-z])$/.exec(raw.toLowerCase());
    const glyph = small ? small[1] : raw.slice(0, 3).toUpperCase() || "?";
    ctx.fillStyle = colour;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `900 ${glyph.length > 1 ? 170 : 250}px system-ui, sans-serif`;
    ctx.fillText(glyph, SIZE / 2, SIZE / 2 + 8);
  }
  ctx.restore();
}

/** The pieces of the shape the child has to cover, as a coarse grid. */
function buildTargets(target: string): Point[] {
  if (isFreeDraw(target)) return [];
  const off = document.createElement("canvas");
  off.width = SIZE;
  off.height = SIZE;
  const ctx = off.getContext("2d", { willReadFrequently: true });
  if (!ctx) return [];
  paintGuide(ctx, target, "#000");

  const { data } = ctx.getImageData(0, 0, SIZE, SIZE);
  const points: Point[] = [];
  for (let y = 0; y < SIZE; y += CELL) {
    for (let x = 0; x < SIZE; x += CELL) {
      let filled = false;
      for (let dy = 0; dy < CELL && !filled; dy += 2) {
        for (let dx = 0; dx < CELL && !filled; dx += 2) {
          if (data[((y + dy) * SIZE + (x + dx)) * 4 + 3] > 40) filled = true;
        }
      }
      if (filled) points.push({ x: x + CELL / 2, y: y + CELL / 2 });
    }
  }
  return points;
}

/**
 * The same pieces, in the order a hand would meet them.
 *
 * `buildTargets` reads the mask row by row, which is the wrong order to show a
 * child: a demo following it would jump left and right across the shape. Walking
 * to the nearest piece not visited yet from the start dot gives one continuous
 * sweep, which is what a finger actually does.
 */
function orderedPath(points: Point[]): Point[] {
  if (points.length < 2) return points.slice();
  const remaining = points.slice(1);
  const path: Point[] = [points[0]!];
  while (remaining.length) {
    const last = path[path.length - 1]!;
    let best = 0;
    let bestDistance = Infinity;
    for (let index = 0; index < remaining.length; index += 1) {
      const candidate = remaining[index]!;
      const dx = candidate.x - last.x;
      const dy = candidate.y - last.y;
      const distance = dx * dx + dy * dy;
      if (distance < bestDistance) {
        bestDistance = distance;
        best = index;
      }
    }
    path.push(remaining.splice(best, 1)[0]!);
  }
  return path;
}

export function TraceCanvas({
  target,
  minAccuracy,
  disabled,
  onComplete,
  onNeedHelp,
  demoSignal = 0
}: {
  target: string;
  minAccuracy: number;
  disabled?: boolean;
  onComplete: () => void;
  /**
   * Asks the guide for a spoken drawing tip. Called when the child taps "Help
   * me", and once by itself when two strokes have gone nowhere — a child who
   * cannot write yet usually cannot ask for help either.
   */
  onNeedHelp?: (question: string) => void;
  /** Bumped by the guide's own "Show me" so both buttons play the same demo. */
  demoSignal?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const targets = useRef<Point[]>([]);
  const covered = useRef<boolean[]>([]);
  const strokes = useRef<Point[][]>([]);
  const drawing = useRef(false);
  const offTarget = useRef(0);
  const drawnCount = useRef(0);
  const finished = useRef(false);
  // Painting reads only refs, never state, so it can be called straight after a
  // change instead of waiting for a re-render. Clearing used to set `coverage`
  // back to 0 when it was already 0 — React skipped the render, the repaint
  // effect never ran, and the canvas kept the child's old strokes on screen.
  const helping = useRef(false);

  // The "watch me" demo: an ordered walk of the shape, a finger dot on the head
  // of it, animated with rAF so the child sees the direction of the stroke.
  const path = useRef<Point[] | null>(null);
  const demoStep = useRef(0);
  const demoPlaying = useRef(false);
  const demoFrame = useRef<number | null>(null);
  const demoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const tries = useRef(0);
  const askedForHelp = useRef(false);

  const [coverage, setCoverage] = useState(0);
  const [wandering, setWandering] = useState(false);
  const [done, setDone] = useState(false);
  const [showingDemo, setShowingDemo] = useState(false);
  /** Free drawing has nothing to measure, so finishing is the child's call. */
  const [hasDrawn, setHasDrawn] = useState(false);

  const { prefersReducedMotion } = useResponsive();
  const { setAvatar } = useAvatar();

  const free = isFreeDraw(target);
  const threshold = Math.min(Math.max(minAccuracy, 0.2), 0.95);

  /** Says a line of coaching out loud. The child cannot read it. */
  const say = useCallback(
    (message: string) => {
      setAvatar({ state: "speaking", message, speak: true, animationEffect: "none", durationMs: null });
    },
    [setAvatar]
  );

  const repaint = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    ctx.clearRect(0, 0, SIZE, SIZE);
    if (!free) paintGuide(ctx, target, "#e2e8f2");

    // The traced parts, in green, so what is left to do is obvious.
    ctx.fillStyle = "#5fb85f";
    targets.current.forEach((point, index) => {
      if (covered.current[index]) {
        ctx.beginPath();
        ctx.arc(point.x, point.y, CELL * 0.72, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    if (helping.current) {
      ctx.fillStyle = "rgba(245, 184, 75, 0.85)";
      targets.current.forEach((point, index) => {
        if (!covered.current[index]) {
          ctx.beginPath();
          ctx.arc(point.x, point.y, CELL * 0.6, 0, Math.PI * 2);
          ctx.fill();
        }
      });
    }

    // The demo trail, and the finger leading it.
    if (demoPlaying.current && path.current) {
      const walked = path.current.slice(0, demoStep.current);
      ctx.fillStyle = "rgba(245, 184, 75, 0.9)";
      walked.forEach((point) => {
        ctx.beginPath();
        ctx.arc(point.x, point.y, CELL * 0.62, 0, Math.PI * 2);
        ctx.fill();
      });
      const head = walked[walked.length - 1];
      if (head) {
        ctx.beginPath();
        ctx.fillStyle = "#4a9dd8";
        ctx.arc(head.x, head.y, 17, 0, Math.PI * 2);
        ctx.fill();
        ctx.lineWidth = 4;
        ctx.strokeStyle = "#fff";
        ctx.stroke();
      }
    }

    // Where to begin: the highest point of the shape, leftmost on a tie.
    const start = targets.current[0];
    if (start && strokes.current.length === 0) {
      ctx.fillStyle = "#4a9dd8";
      ctx.beginPath();
      ctx.arc(start.x, start.y, 13, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.font = "900 15px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("1", start.x, start.y + 1);
    }

    ctx.strokeStyle = "#25313f";
    ctx.lineWidth = STROKE;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    strokes.current.forEach((stroke) => {
      if (stroke.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(stroke[0].x, stroke[0].y);
      stroke.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
      ctx.stroke();
    });
  }, [free, target]);

  const stopDemo = useCallback(() => {
    if (demoFrame.current !== null) {
      window.cancelAnimationFrame(demoFrame.current);
      demoFrame.current = null;
    }
    if (demoTimer.current) {
      clearTimeout(demoTimer.current);
      demoTimer.current = null;
    }
    demoPlaying.current = false;
    helping.current = false;
    setShowingDemo(false);
  }, []);

  /** Wipes the drawing and paints the empty page immediately. */
  const clear = useCallback(() => {
    stopDemo();
    targets.current = buildTargets(target);
    path.current = null;
    covered.current = targets.current.map(() => false);
    strokes.current = [];
    offTarget.current = 0;
    drawnCount.current = 0;
    finished.current = false;
    helping.current = false;
    setCoverage(0);
    setWandering(false);
    setDone(false);
    setHasDrawn(false);
    repaint();
  }, [target, repaint, stopDemo]);

  // A new shape is a new attempt: the tries and the one automatic offer of help
  // belong to the shape, not to the lifetime of the component.
  useEffect(() => {
    tries.current = 0;
    askedForHelp.current = false;
  }, [target]);

  /**
   * Sizes the backing store to the space the canvas actually occupies.
   *
   * The canvas is fluid — it fills its column on a phone and stops at its
   * maximum on a desktop — so a fixed 320px buffer was either blurry or wasted.
   * Drawing keeps working in the 0–320 logical space; only the transform moves.
   */
  const resize = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const shown = canvas.getBoundingClientRect().width || SIZE;
    const scale = (shown / SIZE) * (window.devicePixelRatio || 1);
    canvas.width = Math.round(SIZE * scale);
    canvas.height = Math.round(SIZE * scale);
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    repaint();
  }, [repaint]);

  useEffect(() => {
    clear();
    resize();
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", resize);
      return () => window.removeEventListener("resize", resize);
    }
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [clear, resize]);

  useEffect(() => () => stopDemo(), [stopDemo]);

  /**
   * Walks the shape with a finger dot, then leaves the page as it was.
   *
   * With reduced motion the walk is replaced by the older flash of everything
   * still to trace: the same information, none of the movement.
   */
  const watchMe = useCallback(() => {
    if (disabled || done) return;
    stopDemo();
    // Nothing to demonstrate on a blank page — there the coaching is the
    // invitation itself.
    if (free) {
      say("Draw anything you like! A line, a circle, a big scribble.");
      return;
    }
    say(`Watch me. ${strokeWords(target)}`);

    if (prefersReducedMotion) {
      helping.current = true;
      repaint();
      demoTimer.current = setTimeout(() => {
        helping.current = false;
        repaint();
      }, 1800);
      return;
    }

    if (!path.current) path.current = orderedPath(targets.current);
    const walk = path.current;
    if (!walk.length) return;

    demoPlaying.current = true;
    demoStep.current = 0;
    setShowingDemo(true);
    const stride = Math.max(1, Math.ceil(walk.length / DEMO_FRAMES));

    const tick = () => {
      demoStep.current = Math.min(walk.length, demoStep.current + stride);
      repaint();
      if (demoStep.current >= walk.length) {
        demoTimer.current = setTimeout(() => {
          demoPlaying.current = false;
          setShowingDemo(false);
          repaint();
        }, 700);
        return;
      }
      demoFrame.current = window.requestAnimationFrame(tick);
    };
    demoFrame.current = window.requestAnimationFrame(tick);
  }, [disabled, done, free, prefersReducedMotion, repaint, say, stopDemo, target]);

  // The guide's own "Show me" plays the same demo, so the child gets one
  // answer to "help me draw this" no matter which button they found.
  const firstSignal = useRef(demoSignal);
  useEffect(() => {
    if (demoSignal === firstSignal.current) return;
    firstSignal.current = demoSignal;
    watchMe();
  }, [demoSignal, watchMe]);

  function askGuide() {
    if (!onNeedHelp) return;
    askedForHelp.current = true;
    onNeedHelp(
      free
        ? "I have an empty page for drawing. What could I draw?"
        : `I am learning to write ${target.replace(/_/g, " ")}. Show me how to draw it.`
    );
    watchMe();
  }

  function positionOf(event: React.PointerEvent<HTMLCanvasElement>): Point {
    const rect = event.currentTarget.getBoundingClientRect();
    // x and y are scaled by their own edge. They used to share `rect.width`,
    // which was right only while the canvas was a fixed square — the moment it
    // became fluid, every touch landed above or below where the finger was.
    return {
      x: ((event.clientX - rect.left) / (rect.width || SIZE)) * SIZE,
      y: ((event.clientY - rect.top) / (rect.height || SIZE)) * SIZE
    };
  }

  function mark(point: Point) {
    let hitSomething = false;
    targets.current.forEach((candidate, index) => {
      const dx = candidate.x - point.x;
      const dy = candidate.y - point.y;
      if (dx * dx + dy * dy <= REACH * REACH) {
        hitSomething = true;
        covered.current[index] = true;
      }
    });
    drawnCount.current += 1;
    if (!hitSomething) offTarget.current += 1;
  }

  function start(event: React.PointerEvent<HTMLCanvasElement>) {
    if (disabled || done) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    stopDemo();
    drawing.current = true;
    const point = positionOf(event);
    strokes.current.push([point]);
    mark(point);
    repaint();
  }

  function move(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return;
    const point = positionOf(event);
    strokes.current[strokes.current.length - 1]?.push(point);
    mark(point);
    repaint();
  }

  function end() {
    if (!drawing.current) return;
    drawing.current = false;

    // A free page has no shape to score against. The child says when the
    // drawing is finished, and nothing here judges what they made.
    if (free) {
      setHasDrawn(strokes.current.some((stroke) => stroke.length > 1));
      return;
    }

    const total = targets.current.length || 1;
    const hit = covered.current.filter(Boolean).length;
    const next = hit / total;
    const spill = drawnCount.current ? offTarget.current / drawnCount.current : 0;
    const lost = spill > MAX_SPILL && next < threshold;

    setCoverage(next);
    setWandering(lost);

    if (next >= threshold && spill <= MAX_SPILL && !finished.current) {
      finished.current = true;
      setDone(true);
      // Celebrated, but silently: the lesson speaks its own praise a moment
      // later, and two happy voices at once means the child hears neither.
      setAvatar({ state: "celebrating", message: "You wrote it!", animationEffect: "star_burst", durationMs: 1600 });
      window.setTimeout(onComplete, 900);
      return;
    }

    // Two strokes that went nowhere: show the child how, without waiting for
    // them to ask. A child who cannot write the letter usually cannot ask for
    // help with it either.
    tries.current += 1;
    if (tries.current >= 2 && (lost || next < threshold * 0.6) && !askedForHelp.current) {
      askedForHelp.current = true;
      watchMe();
      onNeedHelp?.(`I am learning to write ${target.replace(/_/g, " ")}. Show me how to draw it.`);
    }
  }

  const percent = Math.round((coverage / threshold) * 100);

  return (
    <div className="grid justify-items-center gap-4">
      {/* Fluid: fills the column on a phone, stops at a comfortable square on a
          bigger screen, and shrinks again on a phone held sideways where the
          height, not the width, is what runs out. */}
      <canvas
        ref={canvasRef}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
        onPointerLeave={end}
        data-testid="trace-canvas"
        data-mode={free ? "free" : "trace"}
        aria-label={free ? "Draw anything" : `Trace ${target}`}
        style={{ touchAction: "none" }}
        className={`aspect-square w-full max-w-[20rem] rounded-[2rem] border-2 bg-white shadow-soft sm:max-w-[22rem] lg:max-w-[24rem] landscape:short:max-w-[13rem] ${
          free ? "border-dashed border-sunshine" : "border-sky/20"
        }`}
      />

      <div className="grid w-full max-w-[24rem] gap-2">
        {/* Progress is coverage of the shape — a free page has none to show. */}
        {free ? null : (
          <div className="h-4 w-full overflow-hidden rounded-full bg-sky/10">
            <div
              className="h-full rounded-full bg-leaf transition-[width] duration-200"
              style={{ width: `${Math.min(percent, 100)}%` }}
            />
          </div>
        )}
        <p aria-live="polite" className="text-center text-base font-black text-ink/70">
          {free
            ? hasDrawn
              ? "Lovely! Tap ✅ when your drawing is done."
              : "Draw anything you like! 🎨"
            : done
              ? "🎉 You wrote it!"
              : showingDemo
                ? "👀 Watch my finger…"
                : wandering
                  ? "Stay on the grey shape. ✏️"
                  : coverage === 0
                    ? "Start on the blue dot. 👆"
                    : "Keep going! 💚"}
        </p>
      </div>

      <div className="touch-row flex w-full max-w-[24rem] flex-wrap justify-center gap-3">
        {free ? (
          <button
            type="button"
            onClick={() => {
              setDone(true);
              onComplete();
            }}
            disabled={disabled || done || !hasDrawn}
            data-testid="trace-finished"
            className="pressable rounded-full bg-leaf px-5 py-3 text-base font-black text-white shadow-soft disabled:opacity-50"
          >
            ✅ I finished
          </button>
        ) : (
          <button
            type="button"
            onClick={watchMe}
            disabled={disabled || done}
            data-testid="trace-watch-me"
            className="pressable rounded-full bg-sunshine px-5 py-3 text-base font-black text-ink shadow-soft disabled:opacity-50"
          >
            👀 Watch me
          </button>
        )}
        {onNeedHelp ? (
          <button
            type="button"
            onClick={askGuide}
            disabled={disabled || done}
            data-testid="trace-help"
            className="pressable rounded-full bg-sky px-5 py-3 text-base font-black text-white shadow-soft disabled:opacity-50"
          >
            🙋 Help me draw
          </button>
        ) : null}
        <button
          type="button"
          onClick={clear}
          disabled={disabled || done}
          data-testid="trace-clear"
          className="pressable rounded-full bg-white px-5 py-3 text-base font-black text-ink shadow-soft disabled:opacity-50"
        >
          🧽 Clear
        </button>
      </div>
    </div>
  );
}
