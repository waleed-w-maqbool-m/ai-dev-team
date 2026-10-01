// Work packets: the one "physical" thing on stage. In the Theater a packet
// is spawned for every real hand-off between agents; on the Story page one
// scripted packet is scrubbed along LINE_STEPS by scroll.
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { sceneSignals, useUi } from "../app/uiStore";
import { useRun } from "../data/runStore";
import type { Handoff } from "../data/runReducer";
import { EDGES, edgeCurve, routeBetween, type EdgeKey } from "./layout";
import { ribbonState } from "./Ribbons";
import { useNoRaycast } from "./noRaycast";
import { COLORS, fire } from "./stageState";
import { LINE_STEPS, lineStepAt } from "./storyScript";

const KIND_COLOR: Record<Handoff["kind"], THREE.Color> = {
  forward: COLORS.accent,
  reject: COLORS.fail,
  pass: COLORS.pass,
  clarify: COLORS.glow,
};

interface Flight {
  route: EdgeKey[];
  kind: Handoff["kind"];
  start: number;
  duration: number;
}

const TRAIL = 5;
const POOL = 3;

/** Smooth start, firm arrival — the packet is "handed over", not thrown. */
const travelEase = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/** Spring-like landing squash after arrival (stiffness ~180, damping ~22). */
function landing(sinceArrival: number): number {
  if (sinceArrival < 0) return 1;
  return 1 + Math.exp(-sinceArrival * 9) * Math.sin(sinceArrival * 22) * 0.35;
}

export function Packets() {
  const mobile = useUi((s) => s.isMobile);
  const reduced = useUi((s) => s.reducedMotion);
  const curves = useMemo(
    () => Object.fromEntries((Object.keys(EDGES) as EdgeKey[]).map((k) => [k, edgeCurve(EDGES[k], mobile)])) as Record<EdgeKey, THREE.CatmullRomCurve3>,
    [mobile],
  );
  const flights = useRef<Flight[]>([]);
  const clock = useRef(0);
  const groups = useRef<(THREE.Group | null)[]>([]);
  const mats = useMemo(
    () => Array.from({ length: POOL }, () => Array.from({ length: TRAIL }, (_, i) =>
      new THREE.MeshBasicMaterial({ color: COLORS.accent.clone(), toneMapped: false, transparent: true, opacity: 1 - i / TRAIL }))),
    [],
  );
  const lastStoryStep = useRef(-1);
  const tmp = useMemo(() => new THREE.Vector3(), []);
  const root = useRef<THREE.Group>(null);
  useNoRaycast(root);

  // Theater: one flight per real hand-off.
  useEffect(
    () =>
      useRun.subscribe((s, prev) => {
        const h = s.view.lastHandoff;
        if (!h || h === prev.view.lastHandoff || sceneSignals.mode !== "theater") return;
        const route = routeBetween(h.from, h.to);
        if (!route.length) return;
        const duration = (reduced ? 0.35 : 1.15) * route.length / Math.max(1, s.speed);
        flights.current = [...flights.current.slice(-(POOL - 1)), { route, kind: h.kind, start: clock.current, duration }];
        for (const k of route) {
          ribbonState.heatTarget[k] = 1.6;
          ribbonState.tint[k].copy(KIND_COLOR[h.kind]);
        }
      }),
    [reduced],
  );

  // Arrival flashes for live runs / replays (Testing core, QA lens).
  useEffect(
    () =>
      useRun.subscribe((s, prev) => {
        if (s.view.events.length <= prev.view.events.length || sceneSignals.mode !== "theater") return;
        const e = s.view.events[s.view.events.length - 1];
        if (e.type === "test_report") fire("testing", e.verdict === "pass" ? COLORS.pass : COLORS.fail);
        if (e.type === "review") fire("qa", e.verdict === "pass" ? COLORS.pass : COLORS.fail);
      }),
    [],
  );

  const pointOnRoute = (route: EdgeKey[], t: number, out: THREE.Vector3) => {
    const scaled = Math.min(0.9999, Math.max(0, t)) * route.length;
    const i = Math.floor(scaled);
    return curves[route[i]].getPointAt(scaled - i, out);
  };

  useFrame((_, dt) => {
    clock.current += dt;
    const story = sceneSignals.mode === "story";

    // Story: a single scripted packet, scrubbed by scroll.
    let storyFlight: { route: EdgeKey[]; kind: Handoff["kind"]; t: number } | null = null;
    if (story) {
      const at = lineStepAt(sceneSignals.storyTime);
      if (at) {
        const step = LINE_STEPS[at.index];
        const t = Math.min(1, at.t / 0.8); // travel, then dwell at the station
        storyFlight = { route: [step.edge], kind: step.kind, t: travelEase(t) };
        ribbonState.heatTarget[step.edge] = Math.max(ribbonState.heatTarget[step.edge], 1.4);
        ribbonState.tint[step.edge].copy(KIND_COLOR[step.kind]);
        // Fire the arrival once per forward crossing of the step.
        if (step.arrive && at.t > 0.82 && lastStoryStep.current !== at.index) {
          fire(step.arrive.agent, step.arrive.result === "pass" ? COLORS.pass : COLORS.fail);
          lastStoryStep.current = at.index;
        }
        if (at.t < 0.5 && lastStoryStep.current === at.index) lastStoryStep.current = -1;
      }
    }

    for (let p = 0; p < POOL; p++) {
      const g = groups.current[p];
      if (!g) continue;
      let route: EdgeKey[] | null = null;
      let kind: Handoff["kind"] = "forward";
      let t = 0;
      let squash = 1;
      if (story) {
        if (p === 0 && storyFlight) ({ route, kind, t } = storyFlight);
      } else {
        const f = flights.current[p];
        if (f) {
          const raw = (clock.current - f.start) / f.duration;
          if (raw < 1.6) {
            route = f.route;
            kind = f.kind;
            t = travelEase(Math.min(1, raw));
            squash = landing((raw - 1) * f.duration);
          }
        }
      }
      g.visible = route !== null;
      if (!route) continue;
      g.children.forEach((child, i) => {
        const lag = i * 0.022;
        pointOnRoute(route!, t - lag, tmp);
        child.position.copy(tmp);
        child.scale.setScalar((i === 0 ? squash : 1) * (1 - i * 0.14));
        const m = mats[p][i];
        m.color.copy(KIND_COLOR[kind]).multiplyScalar(i === 0 ? 3.2 : 1.6);
        child.visible = t - lag > 0;
      });
    }
  });

  return (
    <group ref={root}>
      {Array.from({ length: POOL }, (_, p) => (
        <group key={p} ref={(g) => { groups.current[p] = g; }} visible={false}>
          {Array.from({ length: TRAIL }, (_, i) => (
            <mesh key={i} material={mats[p][i]}>
              <sphereGeometry args={[i === 0 ? 0.075 : 0.05, 16, 16]} />
            </mesh>
          ))}
        </group>
      ))}
    </group>
  );
}
