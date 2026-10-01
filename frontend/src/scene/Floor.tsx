// The stage floor: graphite with faint topographic contour lines (a sense of
// "flow" without decoration) and a baked contact shadow under each plinth —
// cheaper than real-time shadows on an integrated GPU.
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { useUi } from "../app/uiStore";
import { AGENTS } from "../data/types";
import { stationPositions } from "./layout";
import { useNoRaycast } from "./noRaycast";
import { COLORS, stage } from "./stageState";

const vertex = /* glsl */ `
  varying vec3 vWorld;
  void main() {
    vec4 w = modelMatrix * vec4(position, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

const fragment = /* glsl */ `
  uniform vec3 uBg;
  uniform vec3 uLine;
  uniform vec3 uStations[5];
  uniform float uTime;
  uniform float uDim;
  varying vec3 vWorld;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  float fbm(vec2 p) { return noise(p) * 0.65 + noise(p * 2.1 + 3.7) * 0.35; }

  void main() {
    vec2 p = vWorld.xz;
    float h = fbm(p * 0.16 + vec2(uTime * 0.004, 0.0)) * 9.0;
    float d = abs(fract(h) - 0.5) / fwidth(h);
    float contour = 1.0 - min(d, 1.0);

    float r = length(p);
    float fade = smoothstep(16.0, 4.0, r);
    vec3 col = uBg + uLine * contour * 0.055 * fade * (1.0 - uDim * 0.6);

    // Baked contact shadow under each plinth.
    for (int i = 0; i < 5; i++) {
      float s = length(p - uStations[i].xz);
      col *= mix(1.0, 0.45, smoothstep(1.6, 0.9, s));
    }
    gl_FragColor = vec4(col, 1.0);
  }
`;

export function Floor() {
  const ref = useRef<THREE.Mesh>(null);
  useNoRaycast(ref);
  const mobile = useUi((s) => s.isMobile);
  const material = useMemo(() => {
    const pos = stationPositions(mobile);
    return new THREE.ShaderMaterial({
      vertexShader: vertex,
      fragmentShader: fragment,
      uniforms: {
        uBg: { value: COLORS.bg.clone().multiplyScalar(1.35) },
        uLine: { value: COLORS.text.clone() },
        uStations: { value: AGENTS.map((a) => new THREE.Vector3(...pos[a])) },
        uTime: { value: 0 },
        uDim: { value: 0 },
      },
    });
  }, [mobile]);

  useFrame(() => {
    material.uniforms.uTime.value = stage.time;
    material.uniforms.uDim.value = stage.dim;
  });

  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} material={material}>
      <planeGeometry args={[80, 80]} />
    </mesh>
  );
}
