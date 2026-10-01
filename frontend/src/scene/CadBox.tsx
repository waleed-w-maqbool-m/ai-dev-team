// The CAD-style selection frame (reference: Oryzo): dashed bounding box,
// corner handles, a height tick and a mono label. Snaps in on hover or when
// its station is the one working.
import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { useUi } from "../app/uiStore";
import { useRun } from "../data/runStore";
import { AGENT_META, type AgentId } from "../data/types";
import type { Vec3 } from "./layout";
import { useNoRaycast } from "./noRaycast";
import { COLORS, stage } from "./stageState";

// A getter, not a value: this module loads before the .stage element exists.
const stagePortal = {
  get current() {
    return document.querySelector<HTMLElement>(".stage")!;
  },
};

const PHASE_VERB: Record<string, string> = {
  planning: "planning",
  checking: "choosing next task",
  implementing: "writing code",
  clarifying: "asking the PM",
  testing: "running checks",
  reviewing: "reviewing",
  rejected: "rejected, sending back",
  documenting: "writing docs",
};

function useStatus(id: AgentId): string {
  return useRun((s) => {
    if (s.source === "none") return "standing by";
    const v = s.view;
    if (v.activeAgent === id) {
      const task = v.currentTaskId && id !== "pm" && id !== "docs" ? ` ${v.currentTaskId}` : "";
      return `${PHASE_VERB[v.phase] ?? v.phase}${task}`;
    }
    return v.touched.includes(id) ? "done for now" : "waiting";
  });
}

export function CadBox({ id, size }: { id: AgentId; size: Vec3 }) {
  const group = useRef<THREE.Group>(null);
  const label = useRef<HTMLDivElement>(null);
  const shown = useRef(0);
  const [w, h, d] = size;
  const status = useStatus(id);
  useNoRaycast(group);

  const { edges, material, handles } = useMemo(() => {
    const box = new THREE.BoxGeometry(w, h, d);
    const edges = new THREE.EdgesGeometry(box);
    box.dispose();
    const material = new THREE.LineDashedMaterial({
      color: COLORS.text, dashSize: 0.07, gapSize: 0.055, transparent: true, opacity: 0.75, toneMapped: false,
    });
    const handles: Vec3[] = [];
    for (const x of [-w / 2, w / 2]) for (const y of [-h / 2, h / 2]) for (const z of [-d / 2, d / 2]) handles.push([x, y, z]);
    return { edges, material, handles };
  }, [w, h, d]);

  const lineRef = useRef<THREE.LineSegments>(null);
  const handleMat = useMemo(() => new THREE.MeshBasicMaterial({ color: COLORS.accent, toneMapped: false, transparent: true }), []);
  const tickMat = useMemo(() => new THREE.LineBasicMaterial({ color: COLORS.text, transparent: true, toneMapped: false }), []);
  const tick = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const x = w / 2 + 0.22;
    g.setAttribute("position", new THREE.Float32BufferAttribute([
      x, -h / 2, 0, x, h / 2, 0,
      x - 0.06, -h / 2, 0, x + 0.06, -h / 2, 0,
      x - 0.06, h / 2, 0, x + 0.06, h / 2, 0,
    ], 3));
    return g;
  }, [w, h]);

  useFrame((_, dt) => {
    const want = useUi.getState().hovered === id || stage.framed === id ? 1 : 0;
    shown.current = THREE.MathUtils.damp(shown.current, want, want ? 14 : 9, dt);
    const s = shown.current;
    if (!group.current) return;
    group.current.visible = s > 0.01;
    // Snap: arrives slightly oversized and settles, like a selection tool.
    group.current.scale.setScalar(1 + (1 - s) * 0.14);
    material.opacity = 0.75 * s;
    handleMat.opacity = s;
    tickMat.opacity = 0.55 * s;
    if (lineRef.current && lineRef.current.userData.measured !== true) {
      lineRef.current.computeLineDistances();
      lineRef.current.userData.measured = true;
    }
    if (label.current) {
      label.current.style.opacity = String(s);
      label.current.style.transform = `translate3d(0, ${(1 - s) * 6}px, 0)`;
    }
  });

  return (
    <group ref={group} position={[0, h / 2 + 0.1, 0]} visible={false}>
      <lineSegments ref={lineRef} geometry={edges} material={material} />
      {handles.map((p, i) => (
        <mesh key={i} position={p} material={handleMat}>
          <boxGeometry args={[0.055, 0.055, 0.055]} />
        </mesh>
      ))}
      <lineSegments geometry={tick} material={tickMat} />
      {/* Portal into the stage: with a page-wide event source drei would
          otherwise mount labels on #root, above the HUD and outside the
          stage's clipping. */}
      <Html portal={stagePortal} position={[-w / 2, h / 2 + 0.16, 0]} zIndexRange={[20, 10]} pointerEvents="none">
        <div ref={label} className="cad-label" aria-hidden="true">
          <span className="cad-label__name">{AGENT_META[id].name}</span>
          <span className="cad-label__dims">
            W {w.toFixed(2)} · H {h.toFixed(2)} · D {d.toFixed(2)}
          </span>
          <span className="cad-label__status">{status}</span>
        </div>
      </Html>
    </group>
  );
}
