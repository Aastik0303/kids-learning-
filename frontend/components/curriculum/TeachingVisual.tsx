"use client";

/**
 * The picture beside the AI Teacher's explanation.
 *
 * The server names a picture — `letter` / `number` / `count` / `shape` /
 * `colour` and a value — and this draws it. Nothing here renders markup that
 * came from a model: the kinds are a closed set, the value is used as text or
 * as a lookup, and an unknown kind draws nothing at all.
 *
 * SVG rather than emoji because these are the things being *taught*: a letter a
 * child is learning to see, five dots they are learning to count, a triangle
 * whose three corners are the whole lesson. Those have to be big, plain and the
 * same every time, which is exactly what a font's emoji is not.
 */

const PALETTE: Record<string, string> = {
  red: "#e4572e",
  blue: "#2e86de",
  yellow: "#f5b301",
  green: "#3a9d5d",
  orange: "#ef7d31",
  purple: "#8e5bb5",
  pink: "#e86ea4",
  brown: "#8a5a3b",
  black: "#2f3542",
  white: "#ffffff"
};

const INK = "#2f3542";
const SKY = "#dceefb";

export type TeachingVisualProps = {
  kind: string;
  value: string;
  /** Rendered above the picture for a screen reader and for a grown-up. */
  label?: string;
};

export function TeachingVisual({ kind, value, label }: TeachingVisualProps) {
  const drawing = draw(kind, value);
  if (!drawing) return null;

  return (
    <figure className="grid justify-items-center gap-2" data-visual={`${kind}:${value}`}>
      <svg
        viewBox="0 0 200 200"
        role="img"
        aria-label={label ?? describe(kind, value)}
        className="h-40 w-40 sm:h-48 sm:w-48"
      >
        <rect x="4" y="4" width="192" height="192" rx="32" fill={SKY} />
        {drawing}
      </svg>
      <figcaption className="sr-only">{describe(kind, value)}</figcaption>
    </figure>
  );
}

function describe(kind: string, value: string) {
  if (kind === "count") return `${value} things to count`;
  if (kind === "letter") return `The letter ${value}`;
  if (kind === "number") return `The number ${value}`;
  if (kind === "shape") return `A ${value}`;
  if (kind === "colour") return `The colour ${value}`;
  return "";
}

function draw(kind: string, value: string) {
  if (kind === "letter" || kind === "number") {
    return (
      <text
        x="100"
        y="100"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={kind === "letter" || value.length < 2 ? 118 : 96}
        fontWeight="900"
        fill={INK}
        // The letter is the lesson, so it is drawn in whatever font can render
        // it — a Devanagari letter must not fall back to a box.
        fontFamily="system-ui, 'Segoe UI', 'Nirmala UI', sans-serif"
      >
        {value}
      </text>
    );
  }

  if (kind === "count") {
    const total = Math.max(1, Math.min(Number(value) || 1, 10));
    const perRow = total > 5 ? 5 : total;
    const rows = Math.ceil(total / perRow);
    return (
      <g>
        {Array.from({ length: total }, (_, index) => {
          const row = Math.floor(index / perRow);
          const column = index % perRow;
          const inThisRow = Math.min(perRow, total - row * perRow);
          const gap = 168 / (inThisRow + 1);
          return (
            <circle
              key={index}
              cx={16 + gap * (column + 1)}
              cy={rows === 1 ? 100 : 70 + row * 60}
              r={rows === 1 ? 22 : 18}
              fill="#f5b301"
              stroke={INK}
              strokeWidth="3"
            />
          );
        })}
      </g>
    );
  }

  if (kind === "shape") {
    const stroke = { fill: "#ffd166", stroke: INK, strokeWidth: 6 };
    if (value === "circle") return <circle cx="100" cy="100" r="62" {...stroke} />;
    if (value === "square") return <rect x="42" y="42" width="116" height="116" rx="8" {...stroke} />;
    if (value === "rectangle") return <rect x="28" y="62" width="144" height="76" rx="8" {...stroke} />;
    if (value === "triangle") return <polygon points="100,34 168,158 32,158" {...stroke} />;
    if (value === "star") {
      return (
        <polygon
          points="100,30 118,80 172,80 128,112 145,164 100,132 55,164 72,112 28,80 82,80"
          {...stroke}
        />
      );
    }
    return null;
  }

  if (kind === "colour") {
    const fill = PALETTE[value];
    if (!fill) return null;
    return <circle cx="100" cy="100" r="64" fill={fill} stroke={INK} strokeWidth="6" />;
  }

  return null;
}
