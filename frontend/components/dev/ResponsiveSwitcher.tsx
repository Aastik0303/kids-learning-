"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DEVICE_PRESETS, findPreset, readSize, type DevicePreset } from "@/lib/responsive/devices";

/**
 * A viewport switcher for testing the layout, and nothing else.
 *
 * **Why an iframe.** The obvious implementation - put the app in a div and set
 * `width: 390px` - does not work, and worse, it looks as though it does. CSS
 * media queries answer about the *viewport*, not about the box a component sits
 * in, so every `sm:` and `md:` class in the app would keep responding to the
 * real browser window while the box pretended to be a phone. An iframe has a
 * viewport of its own, so the frame at 390px genuinely is 390px: Tailwind's
 * breakpoints fire, `useResponsive` reads 390 from its own `window`, and what
 * you see is what a phone gets.
 *
 * Zoom is a `transform: scale()` on the frame, which shrinks the picture and
 * leaves the frame's viewport where it was - so a 1512px desktop can be
 * inspected on a 1280px laptop without the layout quietly changing underneath
 * the test.
 *
 * **It never runs in production.** `next dev` only, unless somebody sets
 * `NEXT_PUBLIC_RESPONSIVE_SWITCHER=1` deliberately on a staging build. And it
 * refuses to render inside its own frame - `window.self !== window.top` - or
 * the toolbar would recurse forever.
 *
 * Nothing here touches app state. The frame is same-origin, so the session, the
 * active child and every `localStorage` key are shared with the outer tab: you
 * are testing the real app signed in as the real child, not a mock of it.
 */

const STORAGE_KEY = "saksham.dev.viewport";
const ZOOMS = [1, 0.75, 0.5] as const;

type Zoom = (typeof ZOOMS)[number] | "fit";

type Saved = { preset: string; rotated: boolean; zoom: Zoom };

function enabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" ||
    process.env.NEXT_PUBLIC_RESPONSIVE_SWITCHER === "1"
  );
}

function load(): Saved | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Saved>;
    if (!parsed.preset || !findPreset(parsed.preset)) return null;
    return {
      preset: parsed.preset,
      rotated: Boolean(parsed.rotated),
      zoom: parsed.zoom === "fit" || ZOOMS.includes(parsed.zoom as never) ? (parsed.zoom as Zoom) : "fit"
    };
  } catch {
    // A private window, cleared site data, or storage the browser refuses to
    // hand over. The tool simply starts closed.
    return null;
  }
}

function save(value: Saved | null): void {
  try {
    if (value) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage is a convenience here, never a requirement */
  }
}

export function ResponsiveSwitcher() {
  const [ready, setReady] = useState(false);
  const [preset, setPreset] = useState<DevicePreset | null>(null);
  const [rotated, setRotated] = useState(false);
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState({ width: 0, height: 0 });

  const frame = useRef<HTMLIFrameElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  // Fixed for the life of the overlay: re-deriving it on every render would
  // reset the frame's own navigation every time you rotated the device.
  const source = useRef<string>("/");

  // Mount-only. The component reads `window` and `localStorage`, so it renders
  // nothing on the server and nothing on the first client paint either.
  useEffect(() => {
    if (!enabled() || window.self !== window.top) return;
    const saved = load();
    if (saved) {
      setPreset(findPreset(saved.preset));
      setRotated(saved.rotated);
      setZoom(saved.zoom);
    }
    source.current = `${window.location.pathname}${window.location.search}`;
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    save(preset ? { preset: preset.id, rotated, zoom } : null);
  }, [ready, preset, rotated, zoom]);

  // The stage is what is left of the window once the toolbar has its strip.
  useEffect(() => {
    if (!preset) return;
    const element = stageRef.current;
    if (!element) return;
    const measure = () => setStage({ width: element.clientWidth, height: element.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [preset]);

  const size = useMemo(() => {
    if (!preset) return null;
    const width = rotated ? preset.height : preset.width;
    const height = rotated ? preset.width : preset.height;
    return readSize(width, height);
  }, [preset, rotated]);

  const scale = useMemo(() => {
    if (!size) return 1;
    if (zoom !== "fit") return zoom;
    if (!stage.width || !stage.height) return 1;
    // Never scale *up*: a 390px phone blown up to fill a desktop is a lie about
    // how big the text is.
    return Math.min(1, stage.width / size.width, stage.height / size.height);
  }, [size, zoom, stage]);

  /** Leave the frame, and take the outer tab to wherever the frame ended up. */
  const close = useCallback(() => {
    let landing: string | null = null;
    try {
      const inner = frame.current?.contentWindow?.location;
      if (inner) landing = `${inner.pathname}${inner.search}`;
    } catch {
      /* the frame navigated somewhere cross-origin; just close */
    }
    setPreset(null);
    setOpen(false);
    if (landing && landing !== `${window.location.pathname}${window.location.search}`) {
      window.location.href = landing;
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "r") {
        event.preventDefault();
        setOpen((was) => !was);
      }
      if (event.key === "Escape" && preset) close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ready, preset, close]);

  if (!ready) return null;

  const choose = (next: DevicePreset) => {
    if (!preset) source.current = `${window.location.pathname}${window.location.search}`;
    setPreset(next);
    setOpen(true);
  };

  return (
    <>
      {preset && size ? (
        <div className="fixed inset-0 z-[100] flex flex-col bg-slate-900" data-testing-overlay="viewport">
          {/*
            Two boxes, and the split matters. The outer one carries the padding
            and the chequerboard; the inner one is what `stageRef` measures.
            When the padding sat on the measured element, `clientHeight`
            included it - the fit scale came out a little too large, the frame
            overflowed its own box, and `overflow-hidden` quietly clipped a
            strip off the top and bottom. What that ate was the phone's fixed
            bottom navigation bar, so the tool made it look as though the app
            had no way to switch between Class, Levels and Rewards on a phone.
          */}
          <div
            className="flex-1 overflow-hidden p-4"
            style={{
              backgroundImage:
                "linear-gradient(45deg, rgba(255,255,255,.04) 25%, transparent 25%, transparent 75%, rgba(255,255,255,.04) 75%), linear-gradient(45deg, rgba(255,255,255,.04) 25%, transparent 25%, transparent 75%, rgba(255,255,255,.04) 75%)",
              backgroundSize: "24px 24px",
              backgroundPosition: "0 0, 12px 12px"
            }}
          >
            <div
              ref={stageRef}
              className="grid h-full w-full overflow-auto"
              // `safe center` centres the frame while it fits and gives up
              // centring the moment it does not, instead of centring it into
              // its own scroll gutter where the top of it can never be reached.
              // Browsers that do not know the keyword fall back to plain
              // centring, which is what this did before.
              style={{ alignItems: "safe center", justifyItems: "safe center" }}
            >
              {/*
                The sizing box is the *scaled* size; the frame inside it is the
                real one. `transform` does not change layout, so without this
                box a device zoomed to 50% would still reserve its full height
                and the stage would scroll for room nothing occupies.
              */}
              <div style={{ width: size.width * scale, height: size.height * scale, flex: "none" }}>
                <div
                  style={{
                    width: size.width,
                    height: size.height,
                    transform: `scale(${scale})`,
                    transformOrigin: "top left"
                  }}
                  className="overflow-hidden rounded-[1.75rem] border-[10px] border-slate-800 bg-white shadow-2xl"
                >
                  <iframe
                    ref={frame}
                    src={source.current}
                    title={`Saksham IQ at ${size.width} by ${size.height}`}
                    className="h-full w-full border-0"
                  />
                </div>
              </div>
            </div>
          </div>
          <Toolbar
            preset={preset}
            size={size}
            scale={scale}
            zoom={zoom}
            rotated={rotated}
            onChoose={choose}
            onRotate={() => setRotated((was) => !was)}
            onZoom={setZoom}
            onReload={() => {
              // `location.reload()` and not `src = src`: the attribute still
              // holds the route the frame opened on, so re-setting it would
              // throw away wherever you had navigated to inside the frame -
              // which is usually the screen you were trying to reload.
              try {
                frame.current?.contentWindow?.location.reload();
              } catch {
                if (frame.current) frame.current.src = source.current;
              }
            }}
            onClose={close}
          />
        </div>
      ) : null}

      {!preset ? (
        <div
          className="fixed left-3 z-[100] print:hidden"
          style={{ bottom: "calc(2rem + env(safe-area-inset-bottom))" }}
        >
          {open ? (
            <div className="grid gap-2 rounded-2xl bg-slate-900/95 p-3 text-white shadow-2xl ring-1 ring-white/10">
              <div className="flex items-center justify-between gap-4">
                <p className="text-xs font-bold uppercase tracking-wide text-slate-300">Viewport test</p>
                <button
                  className="rounded-lg px-2 py-1 text-xs font-bold text-slate-300 hover:bg-white/10"
                  onClick={() => setOpen(false)}
                >
                  Hide
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {DEVICE_PRESETS.map((item) => (
                  <button
                    key={item.id}
                    title={item.note}
                    onClick={() => choose(item)}
                    className="rounded-lg bg-white/10 px-2.5 py-1.5 text-xs font-bold hover:bg-white/20"
                  >
                    {item.label}
                    <span className="ml-1.5 font-mono text-[10px] text-slate-400">{item.width}</span>
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-slate-400">Ctrl/Cmd + Alt + R toggles this. Dev only.</p>
            </div>
          ) : (
            <button
              onClick={() => setOpen(true)}
              title="Responsive testing (Ctrl/Cmd + Alt + R)"
              className="rounded-full bg-slate-900/90 px-3 py-2 text-xs font-bold text-white shadow-xl ring-1 ring-white/10 hover:bg-slate-900"
            >
              Viewport
            </button>
          )}
        </div>
      ) : null}
    </>
  );
}

function Toolbar({
  preset,
  size,
  scale,
  zoom,
  rotated,
  onChoose,
  onRotate,
  onZoom,
  onReload,
  onClose
}: {
  preset: DevicePreset;
  size: ReturnType<typeof readSize>;
  scale: number;
  zoom: Zoom;
  rotated: boolean;
  onChoose: (preset: DevicePreset) => void;
  onRotate: () => void;
  onZoom: (zoom: Zoom) => void;
  onReload: () => void;
  onClose: () => void;
}) {
  return (
    // Floating rather than welded to the bottom edge. Flush against the very
    // bottom, the bar sits under the operating system's own taskbar or gesture
    // bar and half of it stops being clickable. The 2rem lifts it clear of
    // those, and `env(safe-area-inset-bottom)` adds a phone's home indicator on
    // top when the tool is opened on a real device.
    <div
      className="mx-3 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl bg-slate-950/95 px-3 py-2 text-white shadow-2xl ring-1 ring-white/10 backdrop-blur"
      style={{ marginBottom: "calc(2rem + env(safe-area-inset-bottom))" }}
    >
      <div className="flex flex-wrap gap-1.5">
        {DEVICE_PRESETS.map((item) => (
          <button
            key={item.id}
            title={item.note}
            onClick={() => onChoose(item)}
            aria-pressed={item.id === preset.id}
            className={`rounded-lg px-2.5 py-1.5 text-xs font-bold ${
              item.id === preset.id ? "bg-white text-slate-900" : "bg-white/10 hover:bg-white/20"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1.5">
        <button
          onClick={onRotate}
          aria-pressed={rotated}
          className={`rounded-lg px-2.5 py-1.5 text-xs font-bold ${
            rotated ? "bg-white text-slate-900" : "bg-white/10 hover:bg-white/20"
          }`}
        >
          Rotate
        </button>
        {(["fit", ...ZOOMS] as Zoom[]).map((level) => (
          <button
            key={String(level)}
            onClick={() => onZoom(level)}
            aria-pressed={zoom === level}
            className={`rounded-lg px-2 py-1.5 font-mono text-[11px] font-bold ${
              zoom === level ? "bg-white text-slate-900" : "bg-white/10 hover:bg-white/20"
            }`}
          >
            {level === "fit" ? "fit" : `${level * 100}%`}
          </button>
        ))}
        <button onClick={onReload} className="rounded-lg bg-white/10 px-2.5 py-1.5 text-xs font-bold hover:bg-white/20">
          Reload
        </button>
      </div>

      {/*
        The two readings that actually matter in this codebase, side by side:
        the Tailwind screen the CSS is seeing, and the short-edge bucket
        `useResponsive` is reporting. They are meant to differ in landscape -
        that is the case the layout keeps getting wrong.
      */}
      <div className="flex items-center gap-3 font-mono text-[11px] text-slate-300">
        <span className="text-white">
          {size.width} x {size.height}
        </span>
        <span>@{Math.round(scale * 100)}%</span>
        <span className="rounded bg-sky-500/20 px-1.5 py-0.5 text-sky-200">screen: {size.screen}</span>
        <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-emerald-200">device: {size.device}</span>
        {size.landscape ? <span className="text-amber-300">landscape</span> : null}
        {size.short ? <span className="text-amber-300">short</span> : null}
      </div>

      <button
        onClick={onClose}
        className="ml-auto rounded-lg bg-white px-3 py-1.5 text-xs font-black text-slate-900 hover:bg-slate-200"
      >
        Exit
      </button>
    </div>
  );
}
