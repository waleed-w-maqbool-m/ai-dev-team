// The stage director: decides, every frame, where the camera goes and which
// stations are working, from whichever mode is on screen. Story: scroll
// position (storyTime). Theater: the run store. Pages: a quiet overview.
import { useFrame, useThree } from "@react-three/fiber";
import { useRef, type RefObject } from "react";
import * as THREE from "three";
import { easing } from "maath";

import { sceneSignals, useUi } from "../app/uiStore";
import { useRun } from "../data/runStore";
import { AGENTS, type AgentId } from "../data/types";
import { stationPositions, type Vec3 } from "./layout";
import { stage } from "./stageState";
import { LINE_STEPS, TEAM_ORDER, lineStepAt, teamBeatAt } from "./storyScript";
import { EDGES } from "./layout";

interface Shot {
  pos: Vec3;
  look: Vec3;
}

const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const smooth = (t: number) => t * t * (3 - 2 * t);

function shots(mobile: boolean) {
  const pos = stationPositions(mobile);
  // Team beats frame the station right of centre (desktop) or in the top half
  // (phones), leaving room for the copy.
  const focus = (a: AgentId): Shot =>
    mobile
      ? { pos: add(pos[a], [0.4, 3.4, 5.4]), look: add(pos[a], [0, 0.1, 1.7]) }
      : { pos: add(pos[a], [-0.7, 1.6, 4.5]), look: add(pos[a], [-1.25, 0.95, 0]) };
  return mobile
    ? {
        heroA: { pos: [0, 17, 15], look: [0, 1.5, -1.5] } as Shot,
        heroB: { pos: [0, 15, 13], look: [0, 0.5, 0] } as Shot,
        overview: { pos: [0, 15.5, 11.5], look: [0, 0, 0.6] } as Shot,
        lineEnd: { pos: [0, 14, 10.5], look: [0, 0, 0.6] } as Shot,
        proof: { pos: [0, 22, 17], look: [0, 0, -1] } as Shot,
        dive: { pos: [0, 9, 9], look: [0, 0, 0.5] } as Shot,
        page: { pos: [0, 19, 15], look: [0, 0, 0] } as Shot,
        theater: { pos: [0, 15, 11.5], look: [0, 0, 0.6] } as Shot,
        focus,
        theaterFocus: (a: AgentId): Shot => ({ pos: add(pos[a], [0, 7.5, 6.5]), look: add(pos[a], [0, 0.6, 0]) }),
      }
    : {
        heroA: { pos: [0, 6.9, 15.5], look: [0, 2.1, 0] } as Shot,
        heroB: { pos: [0, 5.8, 12.8], look: [0, 1.3, 0] } as Shot,
        overview: { pos: [0, 6.2, 12.8], look: [0, 0.45, -0.2] } as Shot,
        lineEnd: { pos: [0, 5.5, 11.4], look: [0, 0.45, -0.2] } as Shot,
        // Proof: the stage sinks to the bottom of the frame, away from the facts.
        proof: { pos: [0, 6.2, 17], look: [0, 4.4, 0] } as Shot,
        dive: { pos: [0, 3.4, 7.6], look: [0, 0.6, -0.6] } as Shot,
        page: { pos: [0, 8.5, 17], look: [0, 0.8, 0] } as Shot,
        // Theater: aim right of the action so it centres in the space left of
        // the docked output panel.
        theater: { pos: [1.4, 5.6, 12.4], look: [1.9, 0.55, -0.2] } as Shot,
        focus,
        theaterFocus: (a: AgentId): Shot => ({ pos: add(pos[a], [1.6, 2.6, 7.2]), look: add(pos[a], [1.7, 0.8, 0]) }),
      };
}

/** Keyframes along story time; consecutive equal keys make a hold. */
function storyKeys(mobile: boolean): [number, Shot][] {
  const s = shots(mobile);
  const keys: [number, Shot][] = [[0, s.heroA], [0.9, s.heroB]];
  TEAM_ORDER.forEach((a, i) => {
    const t0 = 1 + i * 0.2;
    keys.push([t0 + 0.05, s.focus(a)], [t0 + 0.15, s.focus(a)]);
  });
  keys.push([2.02, s.overview], [2.9, s.lineEnd], [3.25, s.proof], [4.0, s.proof], [4.85, s.dive]);
  return keys;
}

function sampleKeys(keys: [number, Shot][], t: number, outPos: THREE.Vector3, outLook: THREE.Vector3) {
  if (t <= keys[0][0]) {
    outPos.set(...keys[0][1].pos);
    outLook.set(...keys[0][1].look);
    return;
  }
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, a] = keys[i];
    const [t1, b] = keys[i + 1];
    if (t <= t1) {
      const k = smooth((t - t0) / Math.max(1e-6, t1 - t0));
      outPos.set(...a.pos).lerp(new THREE.Vector3(...b.pos), k);
      outLook.set(...a.look).lerp(new THREE.Vector3(...b.look), k);
      return;
    }
  }
  const last = keys[keys.length - 1][1];
  outPos.set(...last.pos);
  outLook.set(...last.look);
}

export function Director({ rig }: { rig: RefObject<THREE.Group | null> }) {
  const camera = useThree((s) => s.camera);
  const look = useRef(new THREE.Vector3(0, 1, 0));
  const targetPos = useRef(new THREE.Vector3());
  const targetLook = useRef(new THREE.Vector3());
  const tmpA = useRef(new THREE.Vector3());
  const tmpB = useRef(new THREE.Vector3());

  useFrame((_, rawDt) => {
    const dt = Math.min(rawDt, 1 / 20);
    const { isMobile: mobile, reducedMotion: reduced } = useUi.getState();
    const s = shots(mobile);
    stage.time += dt * (reduced ? 0.12 : 1);

    for (const a of AGENTS) {
      stage.activityTarget[a] = 0;
      stage.warmthTarget[a] = 0.08;
    }
    stage.framed = null;
    stage.dimTarget = 0;
    let smoothTime = 1.0;

    if (sceneSignals.mode === "story") {
      let T = sceneSignals.storyTime;
      const beat = teamBeatAt(T);
      if (reduced && beat) T = 1 + beat.index * 0.2 + 0.1; // cut to each beat, no scrub
      sampleKeys(storyKeys(mobile), T, targetPos.current, targetLook.current);
      smoothTime = reduced ? 0.0001 : 0.32;

      if (beat) {
        const a = TEAM_ORDER[beat.index];
        stage.activityTarget[a] = 1;
        stage.framed = a;
      }
      const step = lineStepAt(T);
      if (step) {
        const { edge } = LINE_STEPS[step.index];
        const e = EDGES[edge];
        const at = step.t > 0.62 ? e.to : e.from;
        stage.activityTarget[at] = 1;
        stage.framed = at;
        for (let i = 0; i <= step.index; i++) {
          const st = EDGES[LINE_STEPS[i].edge];
          stage.warmthTarget[st.from] = 0.5;
          if (i < step.index) stage.warmthTarget[st.to] = 0.5;
        }
      }
      if (T >= 3 && T < 4.2) stage.dimTarget = 0.88;
    } else if (sceneSignals.mode === "theater") {
      const { view, source } = useRun.getState();
      const active = view.activeAgent;
      const finished = view.phase === "done" || view.phase === "error";
      for (const a of view.touched) stage.warmthTarget[a] = finished ? 0.9 : 0.5;
      if (source !== "none" && active && !finished) {
        stage.activityTarget[active] = 1;
        stage.framed = active;
        const f = s.theaterFocus(active);
        tmpA.current.set(...s.theater.pos).lerp(tmpB.current.set(...f.pos), 0.55);
        targetPos.current.copy(tmpA.current);
        tmpA.current.set(...s.theater.look).lerp(tmpB.current.set(...f.look), 0.7);
        targetLook.current.copy(tmpA.current);
      } else {
        targetPos.current.set(...s.theater.pos);
        targetLook.current.set(...s.theater.look);
      }
      // Slow drift so the idle stage never looks frozen.
      if (!reduced) targetPos.current.x += Math.sin(stage.time * 0.09) * 0.6;
      smoothTime = reduced ? 0.0001 : 1.0;
    } else {
      targetPos.current.set(...s.page.pos);
      targetLook.current.set(...s.page.look);
      if (!reduced) targetPos.current.x += Math.sin(stage.time * 0.07) * 1.2;
      stage.dimTarget = 0.55;
    }

    for (const a of AGENTS) {
      stage.activity[a] = THREE.MathUtils.damp(stage.activity[a], stage.activityTarget[a], 7, dt);
      stage.warmth[a] = THREE.MathUtils.damp(stage.warmth[a], stage.warmthTarget[a], 1.5, dt);
    }
    stage.dim = THREE.MathUtils.damp(stage.dim, stage.dimTarget, 3, dt);

    easing.damp3(camera.position, targetPos.current, smoothTime, dt);
    easing.damp3(look.current, targetLook.current, smoothTime, dt);
    camera.lookAt(look.current);

    // Whole-stage tilt toward the cursor, damped and clamped to ±6°; it
    // breathes on its own when the cursor is still.
    if (rig.current) {
      const idle = performance.now() - sceneSignals.pointerIdleSince > 2500;
      const breathe = idle && !reduced ? Math.sin(stage.time * 0.45) * 0.35 : 0;
      const p = reduced || mobile ? { x: 0, y: 0 } : sceneSignals.pointer;
      const ry = THREE.MathUtils.degToRad(THREE.MathUtils.clamp(p.x * 6 + breathe * 2, -6, 6));
      const rx = THREE.MathUtils.degToRad(THREE.MathUtils.clamp(-p.y * 2.5 + breathe, -3, 3));
      easing.dampE(rig.current.rotation, [rx, ry, 0], 0.6, dt);
    }
  });

  return null;
}
