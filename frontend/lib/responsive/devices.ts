/**
 * The sizes the responsive switcher can pretend to be, and what each one means
 * to this codebase.
 *
 * A width on its own is not very useful when you are checking a layout here,
 * because Saksham IQ answers *two* different questions about the viewport and
 * they do not agree with each other by design:
 *
 * - **Tailwind `screens`** (`tailwind.config.ts`) are min-width CSS
 *   breakpoints - xs 380, sm 480, md 768, lg 1024, xl 1280 - and they decide
 *   what the classes in the markup do;
 * - **the device bucket** (`breakpoints.ts`) is measured on the *short edge*,
 *   so a phone held sideways is still a phone rather than a tablet, and that is
 *   what `useResponsive` and `AdaptiveStack` read.
 *
 * So the switcher reports both for whatever size is on screen, and the presets
 * below are chosen to land on either side of the interesting edges rather than
 * to be a catalogue of real handsets. The two that matter most are `Phone L`
 * (430px - over the `sm` breakpoint, still a phone by short edge) and any
 * preset rotated into landscape, which is where the two systems disagree and
 * where the layout bugs live.
 *
 * Nothing here is imported by the app itself; it exists for the testing
 * overlay in `components/dev/ResponsiveSwitcher.tsx`.
 */

import { screens } from "@/tailwind.config";
import { resolveDevice, type DeviceBucket } from "./breakpoints";

export type DevicePreset = {
  id: string;
  /** What the button says. */
  label: string;
  /** The family the button is grouped under. */
  family: "phone" | "tablet" | "laptop";
  width: number;
  height: number;
  /** Why this particular size is in the list. */
  note: string;
};

export const DEVICE_PRESETS: readonly DevicePreset[] = [
  {
    id: "phone-s",
    label: "Phone S",
    family: "phone",
    width: 360,
    height: 740,
    note: "Below the xs breakpoint - the narrowest thing that must still work."
  },
  {
    id: "phone",
    label: "Phone",
    family: "phone",
    width: 390,
    height: 844,
    note: "xs. The common handset, and the size to check first."
  },
  {
    id: "phone-l",
    label: "Phone L",
    family: "phone",
    width: 430,
    height: 932,
    note: "Over sm, still a phone by short edge - where the two systems disagree."
  },
  {
    id: "tablet",
    label: "Tablet",
    family: "tablet",
    width: 768,
    height: 1024,
    note: "md, and exactly on the tablet short-edge boundary."
  },
  {
    id: "tablet-l",
    label: "Tablet L",
    family: "tablet",
    width: 1024,
    height: 1366,
    note: "lg. A big tablet reads as desktop by short edge."
  },
  {
    id: "laptop",
    label: "Laptop",
    family: "laptop",
    width: 1280,
    height: 800,
    note: "xl. The smallest laptop worth designing for."
  },
  {
    id: "desktop",
    label: "Desktop",
    family: "laptop",
    width: 1512,
    height: 945,
    note: "A roomy laptop - checks that nothing stretches badly."
  }
] as const;

/** The min-width screens from the Tailwind config, largest first. */
const WIDTH_SCREENS: readonly { name: string; min: number }[] = Object.entries(
  screens as Record<string, string | { raw: string }>
)
  // The `raw` entries - landscape, short, motion - are postures rather than
  // widths, so they are not part of the ladder a pixel count sits on.
  .flatMap(([name, value]) =>
    typeof value === "string" ? [{ name, min: Number.parseInt(value, 10) }] : []
  )
  .filter((entry) => Number.isFinite(entry.min))
  .sort((a, b) => b.min - a.min);

/**
 * Which Tailwind screen a width is inside. `base` when it is under the
 * narrowest one, because that is what mobile-first means: no prefix applies.
 */
export function tailwindScreen(width: number): string {
  return WIDTH_SCREENS.find((entry) => width >= entry.min)?.name ?? "base";
}

export type SizeReading = {
  width: number;
  height: number;
  screen: string;
  device: DeviceBucket;
  landscape: boolean;
  /** Landscape with almost no height - the `short` raw variant. */
  short: boolean;
};

/** Everything the switcher can say about one simulated size, in one place. */
export function readSize(width: number, height: number): SizeReading {
  const landscape = width > height;
  return {
    width,
    height,
    screen: tailwindScreen(width),
    device: resolveDevice(Math.min(width, height)),
    landscape,
    short: landscape && height <= 480
  };
}

export function findPreset(id: string | null): DevicePreset | null {
  if (!id) return null;
  return DEVICE_PRESETS.find((preset) => preset.id === id) ?? null;
}
