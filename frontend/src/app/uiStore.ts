import { create } from "zustand";

import type { AgentId } from "../data/types";

/** Scene quality, stepped down by the performance monitor:
 * 2 = full (bloom + grain), 1 = no bloom, 0 = minimal (DPR 1, fewer particles). */
export type PerfTier = 0 | 1 | 2;

const STORAGE_KEY = "ai-dev-team:reduce-motion";

function initialReducedMotion(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) return stored === "1";
  } catch {
    /* storage unavailable: fall through to the OS setting */
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

interface UiState {
  reducedMotion: boolean;
  setReducedMotion: (on: boolean) => void;
  hovered: AgentId | null;
  setHovered: (agent: AgentId | null) => void;
  perfTier: PerfTier;
  setPerfTier: (tier: PerfTier) => void;
  sceneReady: boolean;
  setSceneReady: () => void;
  isMobile: boolean;
}

export const useUi = create<UiState>((set) => ({
  reducedMotion: initialReducedMotion(),
  setReducedMotion: (on) => {
    try {
      localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
    } catch {
      /* not persisted; still applies for this visit */
    }
    set({ reducedMotion: on });
  },
  hovered: null,
  setHovered: (hovered) => set({ hovered }),
  perfTier: window.matchMedia("(max-width: 760px)").matches ? 0 : 2,
  setPerfTier: (perfTier) => set({ perfTier }),
  sceneReady: false,
  setSceneReady: () => set({ sceneReady: true }),
  isMobile: window.matchMedia("(max-width: 760px)").matches,
}));

// Mirror the setting onto <html> so CSS and non-React code can read it.
const apply = (on: boolean) => (document.documentElement.dataset.motion = on ? "reduced" : "full");
apply(useUi.getState().reducedMotion);
useUi.subscribe((s) => apply(s.reducedMotion));

/** Transient, per-frame values written by scroll handlers and read inside
 * useFrame. Kept out of React state on purpose (no re-renders per frame). */
export const sceneSignals = {
  mode: "story" as "story" | "theater" | "page",
  /** Story page position, 0..5: one unit per section (see storyScript.ts). */
  storyTime: 0,
  /** Normalised pointer, -1..1. */
  pointer: { x: 0, y: 0 },
  pointerIdleSince: 0,
};

window.addEventListener(
  "pointermove",
  (e) => {
    sceneSignals.pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
    sceneSignals.pointer.y = -((e.clientY / window.innerHeight) * 2 - 1);
    sceneSignals.pointerIdleSince = performance.now();
  },
  { passive: true },
);
