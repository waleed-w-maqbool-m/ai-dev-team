import { useFrame } from "@react-three/fiber";
import { useMemo, useRef, type ReactNode } from "react";
import * as THREE from "three";
import { easing } from "maath";

import { useUi } from "../../app/uiStore";
import type { AgentId } from "../../data/types";
import { clay, emissive, setGlow } from "../materials";
import { COLORS, stage } from "../stageState";
import { CadBox } from "../CadBox";
import type { Vec3 } from "../layout";

interface Props {
  id: AgentId;
  position: Vec3;
  /** Width / height / depth of the sculpture, for the CAD frame. */
  size: Vec3;
  children: ReactNode;
}

/** Plinth, ignition ring, hover lift and CAD frame shared by all stations. */
export function Station({ id, position, size, children }: Props) {
  const lift = useRef<THREE.Group>(null);
  const ringMat = useMemo(() => emissive(COLORS.accent), []);
  const setHovered = useUi((s) => s.setHovered);

  useFrame((_, dt) => {
    const hovered = useUi.getState().hovered === id;
    if (lift.current) easing.damp(lift.current.position, "y", hovered ? 0.07 : 0, 0.18, dt);
    const a = stage.activity[id];
    const w = stage.warmth[id];
    setGlow(ringMat, COLORS.accent, (0.18 + w * 0.5 + a * 2.6) * (1 - stage.dim * 0.7));
  });

  return (
    <group position={position} name={`station-${id}`}>
      <group
        ref={lift}
        name={`lift-${id}`}
        onPointerOver={(e) => {
          e.stopPropagation();
          // Events come from the whole page (eventSource = #root); ignore
          // pointers that are really over a HUD panel or button.
          const target = e.nativeEvent.target as Element | null;
          if (target && !target.closest(".stage")) return;
          setHovered(id);
        }}
        // Only clear our own hover: moving between stations can deliver the
        // old pointer-out after the new pointer-over.
        onPointerOut={() => useUi.getState().hovered === id && setHovered(null)}
      >
        {/* Invisible hit volume the size of the CAD frame, so open forms
            (the QA lens aperture, gaps between layers) still take hover. */}
        <mesh visible={false} position={[0, size[1] / 2 + 0.1, 0]}>
          <boxGeometry args={size} />
        </mesh>
        {/* Plinth */}
        <mesh material={clay} position={[0, 0.05, 0]}>
          <cylinderGeometry args={[1.02, 1.08, 0.1, 64]} />
        </mesh>
        <mesh material={ringMat} position={[0, 0.101, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.99, 1.0, 96]} />
        </mesh>
        {children}
      </group>
      <CadBox id={id} size={size} />
    </group>
  );
}
