// The one persistent WebGL canvas, fixed behind every page. Story, Theater
// and the secondary pages all direct this same stage (see Director).
import { PerformanceMonitor } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

import { sceneSignals, useUi } from "../app/uiStore";
import { AGENTS, type AgentId } from "../data/types";
import { Director } from "./Director";
import { Effects } from "./Effects";
import { Floor } from "./Floor";
import { stationPositions } from "./layout";
import { Packets } from "./Packets";
import { Ribbons } from "./Ribbons";
import { COLORS, stage } from "./stageState";
import { Station } from "./stations/Station";
import { Lens, Monolith, Plates, Printer, Reactor } from "./stations/Sculptures";

const DPR: Record<number, [number, number]> = { 2: [1, 1.75], 1: [1, 1.25], 0: [1, 1] };

function Stations({ count }: { count: number }) {
  const mobile = useUi((s) => s.isMobile);
  const pos = stationPositions(mobile);
  const all = [
    <Station key="pm" id="pm" position={pos.pm} size={[1.6, 2.15, 1.6]}><Monolith /></Station>,
    <Station key="swe" id="swe" position={pos.swe} size={[1.14, 1.3, 0.88]}><Printer /></Station>,
    <Station key="testing" id="testing" position={pos.testing} size={[1.12, 1.6, 1.12]}><Reactor /></Station>,
    <Station key="qa" id="qa" position={pos.qa} size={[1.42, 2.2, 0.6]}><Lens /></Station>,
    <Station key="docs" id="docs" position={pos.docs} size={[1.04, 1.05, 0.9]}><Plates /></Station>,
  ];
  return <>{all.slice(0, count)}</>;
}

/** Exposes scene state for the Playwright QA loop (dev builds, or ?qa). */
function DebugRegistry({ rig }: { rig: React.RefObject<THREE.Group | null> }) {
  const { camera, gl, scene } = useThree();
  const frames = useRef(0);
  useFrame(() => {
    frames.current++;
  });
  useEffect(() => {
    const enabled = import.meta.env.DEV || new URLSearchParams(window.location.search).has("qa");
    if (!enabled) return;
    (window as unknown as { __scene: unknown }).__scene = {
      get frames() { return frames.current; },
      get mode() { return sceneSignals.mode; },
      get storyTime() { return sceneSignals.storyTime; },
      get camera() { return camera.position.toArray(); },
      get rig() { return rig.current ? [rig.current.rotation.x, rig.current.rotation.y] : null; },
      get activity() { return { ...stage.activity }; },
      get framed() { return stage.framed; },
      get tier() { return useUi.getState().perfTier; },
      get dpr() { return gl.getPixelRatio(); },
      get gl() { return { geometries: gl.info.memory.geometries, textures: gl.info.memory.textures, calls: gl.info.render.calls }; },
      get hovered() { return useUi.getState().hovered; },
      stations: AGENTS,
      /** Where the centre of a station's sculpture lands on screen (CSS px),
       * for hover tests. Uses its real world-space bounding box. */
      stationScreen(agent: AgentId) {
        const lift = scene.getObjectByName(`lift-${agent}`);
        const v = lift ? new THREE.Box3().setFromObject(lift).getCenter(new THREE.Vector3()) : new THREE.Vector3();
        v.project(camera);
        return [(v.x + 1) / 2 * window.innerWidth, (1 - v.y) / 2 * window.innerHeight];
      },
      /** What a ray through screen point (x, y) hits first: [type, owning station]. */
      pick(x: number, y: number) {
        const rc = new THREE.Raycaster();
        rc.setFromCamera(new THREE.Vector2((x / window.innerWidth) * 2 - 1, -(y / window.innerHeight) * 2 + 1), camera);
        return rc.intersectObjects(scene.children, true).slice(0, 4).map((h) => {
          let o: THREE.Object3D | null = h.object;
          while (o && !o.name.startsWith("station-")) o = o.parent;
          return [h.object.type, o?.name ?? "-", +h.distance.toFixed(2)];
        });
      },
      get renderer() {
        const ctx = gl.getContext();
        const ext = ctx.getExtension("WEBGL_debug_renderer_info");
        return ext ? ctx.getParameter(ext.UNMASKED_RENDERER_WEBGL) : ctx.getParameter(ctx.RENDERER);
      },
    };
  }, [camera, gl, rig, scene]);
  return null;
}

/** Build steps: floor, five stations, ribbons + packets, post-processing. */
const BUILD_STEPS = 8;

function SceneContents() {
  const rig = useRef<THREE.Group>(null);
  const setSceneReady = useUi((s) => s.setSceneReady);
  // The stage is assembled one piece per frame rather than in a single long
  // task, so geometry creation and shader compiles don't block the page
  // (it's also hidden behind the preloader, which waits for the last step).
  const [built, setBuilt] = useState(1);
  useFrame(() => {
    if (built < BUILD_STEPS) setBuilt(built + 1);
    else if (!useUi.getState().sceneReady) requestAnimationFrame(() => setSceneReady());
  });
  return (
    <>
      <color attach="background" args={[COLORS.bg]} />
      <fog attach="fog" args={[COLORS.bg, 16, 38]} />
      <hemisphereLight args={["#c9d2de", "#0a0b0d", 0.55]} />
      <directionalLight position={[4, 9, 6]} intensity={1.7} color="#fff3e8" />
      <directionalLight position={[-7, 3, -6]} intensity={0.9} color="#ffb27a" />
      <directionalLight position={[6, 2, -8]} intensity={0.35} color="#9fb3cc" />
      <group ref={rig}>
        <Floor />
        <Stations count={built - 1} />
        {built >= 7 && <Ribbons />}
        {built >= 7 && <Packets />}
      </group>
      <Director rig={rig} />
      {built >= BUILD_STEPS && <Effects />}
      <DebugRegistry rig={rig} />
    </>
  );
}

export default function Stage({ paused }: { paused: boolean }) {
  const tier = useUi((s) => s.perfTier);
  const setTier = useUi((s) => s.setPerfTier);
  const mobile = useUi((s) => s.isMobile);

  return (
    <div className="stage" aria-hidden="true">
      <Canvas
        dpr={DPR[tier]}
        frameloop={paused ? "demand" : "always"}
        gl={{ antialias: tier > 0, powerPreference: "high-performance", alpha: false, preserveDrawingBuffer: new URLSearchParams(window.location.search).has("qa") }}
        camera={{ fov: mobile ? 52 : 34, near: 0.1, far: 80, position: [0, 6.9, 15.5] }}
        eventSource={document.getElementById("root")!}
        eventPrefix="client"
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.05;
        }}
      >
        <PerformanceMonitor
          onDecline={() => setTier(Math.max(0, useUi.getState().perfTier - 1) as 0 | 1 | 2)}
          flipflops={3}
        >
          <SceneContents />
        </PerformanceMonitor>
      </Canvas>
    </div>
  );
}
