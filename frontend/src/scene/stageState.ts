// Per-frame stage values shared by the scene components. Written by the
// director (StageController) and read in each station's useFrame, so nothing
// here ever triggers a React render.
import * as THREE from "three";

import { AGENTS, type AgentId } from "../data/types";

export const COLORS = {
  bg: new THREE.Color("#07080A"),
  clay: new THREE.Color("#1A1C20"),
  clayLight: new THREE.Color("#24272D"),
  accent: new THREE.Color("#FF5B1F"),
  glow: new THREE.Color("#FFB27A"),
  pass: new THREE.Color("#7CE0C3"),
  fail: new THREE.Color("#FF3B4E"),
  text: new THREE.Color("#ECEAE4"),
};

type PerAgent<T> = Record<AgentId, T>;
const perAgent = <T,>(make: () => T): PerAgent<T> =>
  Object.fromEntries(AGENTS.map((a) => [a, make()])) as PerAgent<T>;

export interface Flash {
  color: THREE.Color;
  at: number; // stage.time when it fired
}

export const stage = {
  time: 0,
  /** 0..1 how hard each station is working right now (damped). */
  activity: perAgent(() => 0),
  activityTarget: perAgent(() => 0),
  /** 0..1 lingering glow for stations that have done work this run. */
  warmth: perAgent(() => 0),
  warmthTarget: perAgent(() => 0),
  flash: perAgent<Flash | null>(() => null),
  /** The station framed by the CAD box (besides hover). */
  framed: null as AgentId | null,
  /** 0..1 global dimming (Proof section, secondary pages). */
  dim: 0,
  dimTarget: 0,
};

export function fire(agent: AgentId, color: THREE.Color) {
  stage.flash[agent] = { color, at: stage.time };
}

/** 1 → 0 over `duration` seconds after a flash, else 0. */
export function flashLevel(agent: AgentId, duration = 0.9): { level: number; color: THREE.Color | null } {
  const f = stage.flash[agent];
  if (!f) return { level: 0, color: null };
  const t = (stage.time - f.at) / duration;
  if (t >= 1) return { level: 0, color: f.color };
  return { level: (1 - t) * (1 - t), color: f.color };
}
