// Light ribbons along every real graph edge (reference: Cerebrium). Idle
// ribbons breathe faintly; one carrying a packet heats up and flows.
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { useUi } from "../app/uiStore";
import { EDGES, edgeCurve, type EdgeKey } from "./layout";
import { useNoRaycast } from "./noRaycast";
import { COLORS, stage } from "./stageState";

/** Per-edge heat (0..1) and tint, written by Packets as they travel. */
export const ribbonState = {
  heat: Object.fromEntries(Object.keys(EDGES).map((k) => [k, 0])) as Record<EdgeKey, number>,
  heatTarget: Object.fromEntries(Object.keys(EDGES).map((k) => [k, 0])) as Record<EdgeKey, number>,
  tint: Object.fromEntries(Object.keys(EDGES).map((k) => [k, COLORS.accent.clone()])) as Record<EdgeKey, THREE.Color>,
};

const vertex = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragment = /* glsl */ `
  uniform float uTime;
  uniform float uHeat;
  uniform float uDim;
  uniform float uOffset;
  uniform vec3 uColor;
  varying vec2 vUv;
  void main() {
    float along = vUv.x;
    // Soft taper at both ends so ribbons emerge from the plinths.
    float ends = smoothstep(0.0, 0.06, along) * smoothstep(1.0, 0.94, along);
    // Faint idle shimmer + a bright pulse train when hot.
    float idle = 0.10 + 0.05 * sin(along * 18.0 - uTime * 1.2 + uOffset);
    float flow = pow(0.5 + 0.5 * sin((along * 9.0 - uTime * 3.2) * 6.2831), 6.0);
    float glow = idle + uHeat * (0.55 + 1.9 * flow);
    gl_FragColor = vec4(uColor * glow * ends * (1.0 - uDim * 0.75), 1.0);
  }
`;

function Ribbon({ k }: { k: EdgeKey }) {
  const mobile = useUi((s) => s.isMobile);
  const geometry = useMemo(() => new THREE.TubeGeometry(edgeCurve(EDGES[k], mobile), 120, 0.013, 6, false), [k, mobile]);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: vertex,
        fragmentShader: fragment,
        uniforms: {
          uTime: { value: 0 },
          uHeat: { value: 0 },
          uDim: { value: 0 },
          uOffset: { value: Math.random() * 6 },
          uColor: { value: COLORS.accent.clone() },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
      }),
    [],
  );

  useFrame((_, dt) => {
    ribbonState.heat[k] = THREE.MathUtils.damp(ribbonState.heat[k], ribbonState.heatTarget[k], 4, dt);
    // Heat decays on its own so a ribbon cools after its packet passes.
    ribbonState.heatTarget[k] = Math.max(0, ribbonState.heatTarget[k] - dt * 0.6);
    material.uniforms.uTime.value = stage.time;
    material.uniforms.uHeat.value = ribbonState.heat[k];
    material.uniforms.uDim.value = stage.dim;
    (material.uniforms.uColor.value as THREE.Color).lerp(ribbonState.tint[k], Math.min(1, dt * 6));
  });

  return <mesh geometry={geometry} material={material} frustumCulled={false} />;
}

export function Ribbons() {
  const ref = useRef<THREE.Group>(null);
  useNoRaycast(ref);
  return (
    <group ref={ref}>
      {(Object.keys(EDGES) as EdgeKey[]).map((k) => (
        <Ribbon key={k} k={k} />
      ))}
    </group>
  );
}
