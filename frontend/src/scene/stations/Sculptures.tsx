// The five sculptural "instruments". Each form says what the agent does;
// all motion is driven from stage.activity / stage.flash in useFrame.
import { RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { useUi } from "../../app/uiStore";
import { clay, clayLight, emissive, setGlow } from "../materials";
import { COLORS, flashLevel, stage } from "../stageState";

const dimmed = (x: number) => x * (1 - stage.dim * 0.7);

/** Project Manager — a monolith with an orbiting ring that spins up while planning. */
export function Monolith() {
  const ring = useRef<THREE.Group>(null);
  const slit = useMemo(() => emissive(), []);
  const ringMat = useMemo(() => emissive(COLORS.glow), []);
  const spin = useRef(0);

  useFrame((_, dt) => {
    const a = stage.activity.pm;
    spin.current += dt * (0.22 + a * 2.8);
    if (ring.current) {
      ring.current.rotation.y = spin.current;
      ring.current.position.y = 1.28 + Math.sin(stage.time * 0.7) * 0.03;
    }
    setGlow(slit, COLORS.accent, dimmed(0.25 + stage.warmth.pm * 0.6 + a * 3));
    setGlow(ringMat, COLORS.glow, dimmed(0.12 + a * 1.6));
  });

  return (
    <group>
      <RoundedBox args={[0.52, 1.9, 0.52]} radius={0.035} smoothness={3} position={[0, 1.05, 0]} material={clay} />
      <mesh position={[0, 1.1, 0.262]} material={slit}>
        <boxGeometry args={[0.032, 1.36, 0.008]} />
      </mesh>
      <mesh position={[0, 2.02, 0]} material={clayLight}>
        <boxGeometry args={[0.6, 0.035, 0.6]} />
      </mesh>
      <group ref={ring}>
        <group rotation={[1.22, 0, 0.18]}>
          <mesh material={ringMat}>
            <torusGeometry args={[0.74, 0.011, 8, 128]} />
          </mesh>
          <mesh position={[0.74, 0, 0]} material={ringMat}>
            <sphereGeometry args={[0.04, 16, 16]} />
          </mesh>
        </group>
      </group>
    </group>
  );
}

const LAYERS = 9;

/** Software Engineer — a printer that extrudes layers upward while writing code. */
export function Printer() {
  const layers = useRef<(THREE.Mesh | null)[]>([]);
  const head = useRef<THREE.Mesh>(null);
  const headMat = useMemo(() => emissive(), []);
  const freshMat = useMemo(() => emissive(COLORS.glow), []);
  const cycle = useRef(0);

  useFrame((_, dt) => {
    const a = stage.activity.swe;
    cycle.current = (cycle.current + dt * (0.08 + a * 0.55)) % 1;
    const printing = 4 + cycle.current * (LAYERS - 4) * Math.min(1, a * 1.5 + 0.15);
    const n = Math.floor(printing);
    layers.current.forEach((m, i) => {
      if (!m) return;
      const grow = i < n ? 1 : i === n ? printing - n : 0;
      m.visible = grow > 0.01;
      m.scale.set(grow, 1, 1);
      m.material = i === n ? freshMat : clayLight;
    });
    if (head.current) head.current.position.y = 0.47 + n * 0.072 + 0.05;
    setGlow(headMat, COLORS.accent, dimmed(0.3 + stage.warmth.swe * 0.5 + a * 2.8));
    setGlow(freshMat, COLORS.glow, dimmed(0.4 + a * 1.4));
  });

  return (
    <group>
      <RoundedBox args={[1.08, 0.34, 0.82]} radius={0.03} smoothness={3} position={[0, 0.27, 0]} material={clay} />
      {[-0.5, 0.5].map((x) => (
        <mesh key={x} position={[x, 0.95, -0.36]} material={clay}>
          <boxGeometry args={[0.045, 1.3, 0.045]} />
        </mesh>
      ))}
      {Array.from({ length: LAYERS }, (_, i) => (
        <mesh key={i} ref={(m) => { layers.current[i] = m; }} position={[0, 0.47 + i * 0.072, 0]} material={clayLight}>
          <boxGeometry args={[0.78, 0.05, 0.56]} />
        </mesh>
      ))}
      <mesh ref={head} position={[0, 0.8, 0]} material={headMat}>
        <boxGeometry args={[1.0, 0.022, 0.05]} />
      </mesh>
    </group>
  );
}

/** Testing Agent — a glass reactor whose core flashes once per check. The
 * only transmissive material in the scene. */
export function Reactor() {
  const core = useRef<THREE.Mesh>(null);
  const coreMat = useMemo(() => emissive(), []);
  const lowPower = useUi((s) => s.perfTier === 0);
  const glass = useMemo(
    () =>
      lowPower
        ? new THREE.MeshStandardMaterial({ color: "#c9d3dc", transparent: true, opacity: 0.12, roughness: 0.1, depthWrite: false })
        : new THREE.MeshPhysicalMaterial({
            color: "#ffffff", transmission: 1, thickness: 0.35, roughness: 0.14, ior: 1.32,
            attenuationColor: new THREE.Color("#ffd9c4"), attenuationDistance: 3, transparent: true,
          }),
    [lowPower],
  );

  useFrame(() => {
    const a = stage.activity.testing;
    const { level, color } = flashLevel("testing", 1.1);
    if (core.current) {
      core.current.position.y = 0.92 + Math.sin(stage.time * (1.2 + a * 5)) * (0.03 + a * 0.06);
      core.current.scale.setScalar(1 + level * 0.45 + a * 0.08);
    }
    setGlow(coreMat, COLORS.accent, dimmed(0.35 + stage.warmth.testing * 0.5 + a * 2.2 + level * 3), color, level);
  });

  return (
    <group>
      <mesh position={[0, 0.17, 0]} material={clay}>
        <cylinderGeometry args={[0.52, 0.56, 0.14, 48]} />
      </mesh>
      <mesh position={[0, 1.64, 0]} material={clay}>
        <cylinderGeometry args={[0.52, 0.5, 0.1, 48]} />
      </mesh>
      {[0, 1, 2].map((i) => (
        <mesh key={i} position={[Math.cos((i / 3) * Math.PI * 2) * 0.3, 0.92, Math.sin((i / 3) * Math.PI * 2) * 0.3]} material={clayLight}>
          <cylinderGeometry args={[0.012, 0.012, 1.3, 8]} />
        </mesh>
      ))}
      <mesh ref={core} position={[0, 0.92, 0]} material={coreMat}>
        <icosahedronGeometry args={[0.15, 3]} />
      </mesh>
      <mesh position={[0, 0.91, 0]} material={glass}>
        <cylinderGeometry args={[0.43, 0.43, 1.34, 64, 1, true]} />
      </mesh>
    </group>
  );
}

/** QA Reviewer — a ring lens; a scan beam sweeps the packet before the verdict. */
export function Lens() {
  const beam = useRef<THREE.Mesh>(null);
  const innerMat = useMemo(() => emissive(), []);
  const beamMat = useMemo(
    () => new THREE.MeshBasicMaterial({ color: COLORS.glow.clone(), transparent: true, opacity: 0, toneMapped: false, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }),
    [],
  );

  useFrame(() => {
    const a = stage.activity.qa;
    const { level, color } = flashLevel("qa", 1.4);
    if (beam.current) beam.current.position.y = 1.46 + Math.sin(stage.time * 3.1) * 0.46;
    beamMat.opacity = dimmed(a * 0.9);
    beamMat.color.copy(COLORS.glow).multiplyScalar(2.2);
    setGlow(innerMat, COLORS.accent, dimmed(0.3 + stage.warmth.qa * 0.5 + a * 2 + level * 3.2), color, level);
  });

  return (
    <group>
      <RoundedBox args={[0.74, 0.12, 0.52]} radius={0.025} smoothness={3} position={[0, 0.16, 0]} material={clay} />
      <mesh position={[0, 0.55, 0]} material={clay}>
        <boxGeometry args={[0.12, 0.72, 0.12]} />
      </mesh>
      <mesh position={[0, 1.46, 0]} material={clay}>
        <torusGeometry args={[0.62, 0.085, 24, 96]} />
      </mesh>
      <mesh position={[0, 1.46, 0.04]} material={innerMat}>
        <torusGeometry args={[0.515, 0.009, 8, 128]} />
      </mesh>
      <mesh ref={beam} position={[0, 1.46, 0]} material={beamMat}>
        <planeGeometry args={[1.0, 0.018]} />
      </mesh>
    </group>
  );
}

const PLATES = 7;

/** Documentation — a stack of plates that fans open like pages. */
export function Plates() {
  const plates = useRef<(THREE.Group | null)[]>([]);
  const edgeMat = useMemo(() => emissive(), []);
  const fan = useRef(0);

  useFrame((_, dt) => {
    const a = stage.activity.docs;
    const target = a * (0.75 + Math.sin(stage.time * 1.4) * 0.25) + stage.warmth.docs * 0.15;
    fan.current = THREE.MathUtils.damp(fan.current, target, 3, dt);
    plates.current.forEach((g, i) => {
      if (g) g.rotation.x = -fan.current * i * 0.085;
    });
    setGlow(edgeMat, COLORS.accent, dimmed(0.3 + stage.warmth.docs * 0.6 + a * 2.6));
  });

  return (
    <group position={[0, 0, 0.06]}>
      <mesh position={[-0.5, 0.44, 0]} material={clay}>
        <boxGeometry args={[0.06, 0.62, 0.7]} />
      </mesh>
      {Array.from({ length: PLATES }, (_, i) => (
        <group key={i} ref={(g) => { plates.current[i] = g; }} position={[0, 0.2 + i * 0.075, -0.34]}>
          <RoundedBox args={[0.94, 0.034, 0.68]} radius={0.012} smoothness={2} position={[0, 0, 0.34]} material={i % 2 ? clayLight : clay} />
          {i === PLATES - 1 && (
            <mesh position={[0, 0.02, 0.68]} material={edgeMat}>
              <boxGeometry args={[0.94, 0.012, 0.012]} />
            </mesh>
          )}
        </group>
      ))}
    </group>
  );
}
