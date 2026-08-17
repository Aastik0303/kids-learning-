"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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
 * Accuracy is measured here on the device, from the gesture, exactly as the
 * curriculum contract requires: no model is asked whether the writing is good.
 * Coverage is how much of the shape was touched; spill is how much of the
 * child's drawing landed nowhere near it, so scribbling over the whole box does
 * not pass.
 */

const SIZE = 320; // logical canvas size, in CSS pixels
const CELL = 8; // resolution of the target mask
const REACH = 20; // how near a finger must pass for a piece to count as traced
const STROKE = 26; // how thick the child's line is drawn
const MAX_SPILL = 0.45; // beyond this, the drawing is not following the shape

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

export function TraceCanvas({
  target,
  minAccuracy,
  disabled,
  onComplete
}: {
  target: string;
  minAccuracy: number;
  disabled?: boolean;
  onComplete: () => void;
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

  const [coverage, setCoverage] = useState(0);
  const [wandering, setWandering] = useState(false);
  const [done, setDone] = useState(false);

  const threshold = Math.min(Math.max(minAccuracy, 0.2), 0.95);

  const repaint = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    ctx.clearRect(0, 0, SIZE, SIZE);
    paintGuide(ctx, target, "#e2e8f2");

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
  }, [target]);

  /** Wipes the drawing and paints the empty page immediately. */
  const clear = useCallback(() => {
    targets.current = buildTargets(target);
    covered.current = targets.current.map(() => false);
    strokes.current = [];
    offTarget.current = 0;
    drawnCount.current = 0;
    finished.current = false;
    helping.current = false;
    setCoverage(0);
    setWandering(false);
    setDone(false);
    repaint();
  }, [target, repaint]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = SIZE * ratio;
    canvas.height = SIZE * ratio;
    canvas.getContext("2d")?.scale(ratio, ratio);
    clear();
  }, [clear]);

  /** Flashes the part still to be traced, then goes back to the plain page. */
  const showMe = useCallback(() => {
    helping.current = true;
    repaint();
    window.setTimeout(() => {
      helping.current = false;
      repaint();
    }, 1600);
  }, [repaint]);

  function positionOf(event: React.PointerEvent<HTMLCanvasElement>): Point {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * SIZE,
      y: ((event.clientY - rect.top) / rect.height) * SIZE
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
    drawing.current = true;
    helping.current = false;
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

    const total = targets.current.length || 1;
    const hit = covered.current.filter(Boolean).length;
    const next = hit / total;
    const spill = drawnCount.current ? offTarget.current / drawnCount.current : 0;

    setCoverage(next);
    setWandering(spill > MAX_SPILL && next < threshold);

    if (next >= threshold && spill <= MAX_SPILL && !finished.current) {
      finished.current = true;
      setDone(true);
      window.setTimeout(onComplete, 900);
    }
  }

  const percent = Math.round((coverage / threshold) * 100);

  return (
    <div className="grid justify-items-center gap-4">
      <canvas
        ref={canvasRef}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
        onPointerLeave={end}
        data-testid="trace-canvas"
        aria-label={`Trace ${target}`}
        style={{ width: SIZE, height: SIZE, touchAction: "none" }}
        className="max-w-full rounded-[2rem] border-2 border-sky/20 bg-white shadow-soft"
      />

      <div className="grid w-full max-w-[20rem] gap-2">
        <div className="h-4 w-full overflow-hidden rounded-full bg-sky/10">
          <div
            className="h-full rounded-full bg-leaf transition-[width] duration-200"
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
        <p aria-live="polite" className="text-center text-base font-black text-ink/70">
          {done
            ? "🎉 You wrote it!"
            : wandering
              ? "Stay on the grey shape. ✏️"
              : coverage === 0
                ? "Start on the blue dot. 👆"
                : "Keep going! 💚"}
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={showMe}
          disabled={disabled || done}
          className="pressable rounded-full bg-sunshine px-5 py-3 text-base font-black text-ink shadow-soft disabled:opacity-50"
        >
          ✨ Show me
        </button>
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
