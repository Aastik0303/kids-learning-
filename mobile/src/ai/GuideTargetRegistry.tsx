import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import type { View } from "react-native";

/**
 * The allowlist of UI elements the AI is permitted to point at
 * (spec section 11).
 *
 * A component becomes AI-addressable only by calling `useGuideTarget`,
 * which registers an id here. The guide agent is told the ids that are
 * currently on screen, and any target it names that is not in this
 * registry is discarded before it reaches the UI.
 *
 * This is a runtime registry rather than a static list because the valid
 * set changes per screen — "triangle-option" only exists while a shape
 * question is mounted.
 */

export type GuideTargetKind =
  /** A tappable answer option. */
  | "option"
  /** A visual item being counted or examined. */
  | "visual"
  /** A control: microphone, continue, hint. */
  | "control"
  /** A navigation affordance: a class card, a level node. */
  | "nav"
  /** The drawing/tracing surface. */
  | "canvas";

export type RegisteredTarget = {
  id: string;
  kind: GuideTargetKind;
  /** Human label, included in the guide payload so the LLM knows what it is. */
  label: string;
  ref: React.RefObject<View | null>;
};

type RegistryValue = {
  register: (target: RegisteredTarget) => () => void;
  /** Ids currently mounted — sent as `available_targets`. */
  targetIds: () => string[];
  /** Visual-only ids — sent as `allowed_visual_targets`. */
  visualTargetIds: () => string[];
  get: (id: string) => RegisteredTarget | undefined;
  has: (id: string) => boolean;
  labelled: () => Array<{ id: string; label: string; kind: GuideTargetKind }>;
};

const GuideTargetContext = createContext<RegistryValue | null>(null);

export function GuideTargetRegistryProvider({ children }: { children: ReactNode }) {
  // A ref, not state: registration happens during layout and must not
  // trigger a re-render storm as a lesson mounts a dozen targets.
  const targets = useRef(new Map<string, RegisteredTarget>());

  const register = useCallback((target: RegisteredTarget) => {
    targets.current.set(target.id, target);
    return () => {
      targets.current.delete(target.id);
    };
  }, []);

  const value = useMemo<RegistryValue>(
    () => ({
      register,
      targetIds: () => Array.from(targets.current.keys()),
      visualTargetIds: () =>
        Array.from(targets.current.values())
          .filter((target) => target.kind === "visual" || target.kind === "option")
          .map((target) => target.id),
      get: (id) => targets.current.get(id),
      has: (id) => targets.current.has(id),
      labelled: () =>
        Array.from(targets.current.values()).map(({ id, label, kind }) => ({ id, label, kind })),
    }),
    [register],
  );

  return <GuideTargetContext.Provider value={value}>{children}</GuideTargetContext.Provider>;
}

export function useGuideTargetRegistry(): RegistryValue {
  const value = useContext(GuideTargetContext);
  if (!value) {
    throw new Error("useGuideTargetRegistry must be used inside <GuideTargetRegistryProvider>");
  }
  return value;
}

/**
 * Register a component as an AI-addressable target for as long as it is
 * mounted. Returns the ref to attach to the underlying View.
 *
 *   const ref = useGuideTarget("triangle-option", "option", "Triangle");
 *   return <Pressable ref={ref} ... />
 */
export function useGuideTarget(
  id: string,
  kind: GuideTargetKind,
  label: string,
): React.RefObject<View | null> {
  const registry = useGuideTargetRegistry();
  const ref = useRef<View | null>(null);

  useEffect(() => {
    return registry.register({ id, kind, label, ref });
  }, [registry, id, kind, label]);

  return ref;
}
