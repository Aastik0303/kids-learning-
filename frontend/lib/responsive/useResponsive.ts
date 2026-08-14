"use client";

import { useSyncExternalStore } from "react";
import { deviceIndex, resolveDevice, type DeviceBucket } from "./breakpoints";

export type ResponsiveState = {
  width: number;
  height: number;
  /** The shorter of the two edges — what device bucketing is measured on. */
  shortEdge: number;
  device: DeviceBucket;
  isPhone: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isLandscape: boolean;
  /** Landscape with almost no vertical room — a phone held sideways. */
  isShort: boolean;
  prefersReducedMotion: boolean;
};

/**
 * Server snapshot. Rendered markup must match on the client's first paint or
 * React throws a hydration mismatch, so the server always assumes the phone
 * case — the mobile-first default, and the safest thing to show first.
 */
const SERVER_SNAPSHOT: ResponsiveState = {
  width: 0,
  height: 0,
  shortEdge: 0,
  device: "phone",
  isPhone: true,
  isTablet: false,
  isDesktop: false,
  isLandscape: false,
  isShort: false,
  prefersReducedMotion: false
};

let cached: ResponsiveState = SERVER_SNAPSHOT;

function readSnapshot(): ResponsiveState {
  const width = window.innerWidth;
  const height = window.innerHeight;
  const shortEdge = Math.min(width, height);
  const device = resolveDevice(shortEdge);
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // useSyncExternalStore compares snapshots by reference, so returning a fresh
  // object every call would loop forever. Only allocate when something moved.
  if (
    cached.width === width &&
    cached.height === height &&
    cached.prefersReducedMotion === prefersReducedMotion
  ) {
    return cached;
  }

  cached = {
    width,
    height,
    shortEdge,
    device,
    isPhone: device === "phone",
    isTablet: device === "tablet",
    isDesktop: device === "desktop",
    isLandscape: width > height,
    isShort: width > height && height <= 480,
    prefersReducedMotion
  };
  return cached;
}

function subscribe(onChange: () => void): () => void {
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  window.addEventListener("resize", onChange);
  window.addEventListener("orientationchange", onChange);
  motion.addEventListener("change", onChange);
  return () => {
    window.removeEventListener("resize", onChange);
    window.removeEventListener("orientationchange", onChange);
    motion.removeEventListener("change", onChange);
  };
}

/**
 * Viewport state bucketed on the short edge.
 *
 * Nothing in the app may read `window.innerWidth` directly — go through here,
 * so the short-edge rule holds everywhere and there is one place to test.
 */
export function useResponsive(): ResponsiveState & {
  atLeast: (name: DeviceBucket) => boolean;
  below: (name: DeviceBucket) => boolean;
} {
  const state = useSyncExternalStore(subscribe, readSnapshot, () => SERVER_SNAPSHOT);
  return {
    ...state,
    atLeast: (name) => deviceIndex(state.device) >= deviceIndex(name),
    below: (name) => deviceIndex(state.device) < deviceIndex(name)
  };
}

export type ResponsiveValue<T> = T | Partial<Record<DeviceBucket, T>>;

function isBucketMap<T>(value: ResponsiveValue<T>): value is Partial<Record<DeviceBucket, T>> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  return Object.keys(value).some((key) => key === "phone" || key === "tablet" || key === "desktop");
}

/**
 * Resolve a per-bucket value against the active device, falling back *down*
 * the scale so `{ phone: 1, desktop: 3 }` still answers on tablet.
 */
export function useResponsiveValue<T>(value: ResponsiveValue<T>): T {
  const { device } = useResponsive();
  if (!isBucketMap(value)) return value as T;

  const order: DeviceBucket[] = ["phone", "tablet", "desktop"];
  const active = deviceIndex(device);

  for (let i = active; i >= 0; i -= 1) {
    const candidate = value[order[i]!];
    if (candidate !== undefined) return candidate;
  }
  for (let i = active + 1; i < order.length; i += 1) {
    const candidate = value[order[i]!];
    if (candidate !== undefined) return candidate;
  }
  throw new Error("useResponsiveValue received an empty bucket map");
}
