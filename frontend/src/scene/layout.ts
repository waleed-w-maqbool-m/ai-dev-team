// Where the five stations stand and how the real graph's edges run between
// them. Every ribbon corresponds to an actual edge in graph/build_graph.py.
import * as THREE from "three";

import type { AgentId } from "../data/types";

export type Vec3 = [number, number, number];

const DESKTOP: Record<AgentId, Vec3> = {
  pm: [-5.4, 0, 0.7],
  swe: [-2.7, 0, -0.5],
  testing: [0, 0, -1.0],
  qa: [2.7, 0, -0.5],
  docs: [5.4, 0, 0.7],
};

// Portrait: the line zig-zags toward the camera so it fits a phone screen.
const MOBILE: Record<AgentId, Vec3> = {
  pm: [-1.1, 0, -5.6],
  swe: [1.1, 0, -2.8],
  testing: [-1.1, 0, 0],
  qa: [1.1, 0, 2.8],
  docs: [-1.1, 0, 5.6],
};

export const PORT_HEIGHT = 0.42;

export type EdgeKey =
  | "pm>swe" | "swe>testing" | "testing>qa" | "qa>pm" | "qa>swe" | "swe>pm" | "pm>docs";

export interface EdgeSpec {
  from: AgentId;
  to: AgentId;
  /** Shape of the arc: lift (y) and sideways bulge (z) of the midpoint. */
  lift: number;
  bulge: number;
  role: "forward" | "retry" | "clarify" | "check" | "finish";
}

export const EDGES: Record<EdgeKey, EdgeSpec> = {
  "pm>swe": { from: "pm", to: "swe", lift: 0.35, bulge: 0, role: "forward" },
  "swe>testing": { from: "swe", to: "testing", lift: 0.35, bulge: 0, role: "forward" },
  "testing>qa": { from: "testing", to: "qa", lift: 0.35, bulge: 0, role: "forward" },
  "qa>pm": { from: "qa", to: "pm", lift: 0.15, bulge: 2.6, role: "check" },
  "qa>swe": { from: "qa", to: "swe", lift: 2.4, bulge: -0.4, role: "retry" },
  "swe>pm": { from: "swe", to: "pm", lift: 1.7, bulge: -1.2, role: "clarify" },
  "pm>docs": { from: "pm", to: "docs", lift: 0.9, bulge: -3.4, role: "finish" },
};

export function stationPositions(mobile: boolean): Record<AgentId, Vec3> {
  return mobile ? MOBILE : DESKTOP;
}

export function edgeCurve(spec: EdgeSpec, mobile: boolean): THREE.CatmullRomCurve3 {
  const pos = stationPositions(mobile);
  const a = new THREE.Vector3(...pos[spec.from]).setY(PORT_HEIGHT);
  const b = new THREE.Vector3(...pos[spec.to]).setY(PORT_HEIGHT);
  const mid = a.clone().lerp(b, 0.5);
  // Bulge sideways relative to the edge direction (perpendicular on the floor).
  const dir = b.clone().sub(a).setY(0).normalize();
  const side = new THREE.Vector3(-dir.z, 0, dir.x);
  mid.addScaledVector(side, spec.bulge * (mobile ? 0.45 : 1)).setY(PORT_HEIGHT + spec.lift);
  const q1 = a.clone().lerp(mid, 0.5).setY(PORT_HEIGHT + spec.lift * 0.75);
  const q3 = mid.clone().lerp(b, 0.5).setY(PORT_HEIGHT + spec.lift * 0.75);
  return new THREE.CatmullRomCurve3([a, q1, mid, q3, b], false, "centripetal");
}

/** The ribbons a packet travels to get from one station to another. Usually
 * one edge; a replay recorded before the Testing Agent existed goes
 * SWE → QA directly, which on the stage passes through the reactor. */
export function routeBetween(from: AgentId, to: AgentId): EdgeKey[] {
  const direct = `${from}>${to}` as EdgeKey;
  if (direct in EDGES) return [direct];
  // Breadth-first over the real edges.
  const queue: { at: AgentId; path: EdgeKey[] }[] = [{ at: from, path: [] }];
  const seen = new Set<AgentId>([from]);
  while (queue.length) {
    const { at, path } = queue.shift()!;
    for (const key of Object.keys(EDGES) as EdgeKey[]) {
      const e = EDGES[key];
      if (e.from !== at || seen.has(e.to)) continue;
      const next = [...path, key];
      if (e.to === to) return next;
      seen.add(e.to);
      queue.push({ at: e.to, path: next });
    }
  }
  return [];
}
