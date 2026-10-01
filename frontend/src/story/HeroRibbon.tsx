// The hero's light ribbon (reference: Lusion), weaving behind and in front of
// the real DOM headline. It's a 3D Catmull-Rom curve projected with a 35°
// perspective camera every frame; stroke width follows depth. Drawn as two
// SVG layers — one under the headline, one over it — so the weave is exact
// against live text, and it still works without WebGL.
//
// The maths is written out here rather than imported from three.js so the
// hero doesn't pull the 3D library into the first-load bundle.
import gsap from "gsap";
import { useEffect, useRef } from "react";

import { sceneSignals, useUi } from "../app/uiStore";

type Vec = [number, number, number];

const SAMPLES = 72;
const FOV = (35 * Math.PI) / 180;
const CENTER_Z = -8;

/** Uniform Catmull-Rom through `pts` at u in [0, 1], written into `out`. */
function catmullRom(pts: Vec[], u: number, out: Vec) {
  const n = pts.length - 1;
  const x = Math.min(0.99999, Math.max(0, u)) * n;
  const i = Math.floor(x);
  const t = x - i;
  const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[Math.min(n, i + 1)], p3 = pts[Math.min(n, i + 2)];
  const t2 = t * t, t3 = t2 * t;
  for (let k = 0; k < 3; k++) {
    out[k] = 0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3);
  }
}

/** Rotates `p` by pitch `rx` then yaw `ry` about the point (0, 0, cz). */
function rotateAbout(p: Vec, rx: number, ry: number, cz: number) {
  const y = p[1], z = p[2] - cz;
  const y1 = y * Math.cos(rx) - z * Math.sin(rx);
  const z1 = y * Math.sin(rx) + z * Math.cos(rx);
  const x2 = p[0] * Math.cos(ry) + z1 * Math.sin(ry);
  const z2 = -p[0] * Math.sin(ry) + z1 * Math.cos(ry);
  p[0] = x2; p[1] = y1; p[2] = z2 + cz;
}

/** Signal orange #FF5B1F → glow #FFB27A along the ribbon. */
function lerpHex(u: number): string {
  const g = Math.round(0x5b + (0xb2 - 0x5b) * u);
  const b = Math.round(0x1f + (0x7a - 0x1f) * u);
  return `#ff${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}
/** Parts of the curve (0..1) drawn over the headline; the rest pass behind. */
const FRONT: [number, number][] = [[0.24, 0.37], [0.58, 0.7]];
const isFront = (u: number) => FRONT.some(([a, b]) => u >= a && u <= b);

// Control points in normalised screen space (x, y in -1..1) plus depth.
const CONTROLS: [number, number, number][] = [
  [-1.2, -0.62, -9.5], [-0.78, 0.12, -7.2], [-0.42, 0.42, -8.6], [-0.05, 0.02, -6.4],
  [0.3, 0.36, -8.2], [0.66, 0.06, -6.9], [1.0, 0.5, -8.8], [1.25, 0.2, -10],
];

export function HeroRibbon() {
  const back = useRef<SVGGElement>(null);
  const front = useRef<SVGGElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const ready = useUi((s) => s.sceneReady);
  const reduced = useUi((s) => s.reducedMotion);
  const reveal = useRef({ v: 0 });

  useEffect(() => {
    if (!ready) return;
    if (reduced) {
      reveal.current.v = 1;
      return;
    }
    const tween = gsap.to(reveal.current, { v: 1, duration: 2.2, ease: "expo.out", delay: 0.25 });
    return () => {
      tween.kill();
    };
  }, [ready, reduced]);

  useEffect(() => {
    const backG = back.current;
    const frontG = front.current;
    const el = wrap.current;
    if (!backG || !frontG || !el) return;

    // Two <line>s per sample per layer: a wide faint glow and a bright core.
    const make = (g: SVGGElement) =>
      Array.from({ length: SAMPLES - 1 }, () => {
        const glow = document.createElementNS("http://www.w3.org/2000/svg", "line");
        const core = document.createElementNS("http://www.w3.org/2000/svg", "line");
        glow.setAttribute("class", "ribbon-glow");
        core.setAttribute("class", "ribbon-core");
        g.append(glow, core);
        return { glow, core };
      });
    const layers = { back: make(backG), front: make(frontG) };

    const pts: Vec[] = CONTROLS.map(() => [0, 0, 0]);
    const p: Vec = [0, 0, 0];
    const tilt = { x: 0, y: 0 };
    const drawn = { back: new Array<boolean>(SAMPLES - 1).fill(true), front: new Array<boolean>(SAMPLES - 1).fill(true) };
    let visible = true;
    let raf = 0;

    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting));
    io.observe(el);

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (!visible) return;
      const W = el.clientWidth;
      const H = el.clientHeight;
      const aspect = W / Math.max(1, H);
      const tanH = Math.tan(FOV / 2);
      const t = now / 1000;
      const motion = useUi.getState().reducedMotion ? 0 : 1;

      // On portrait screens the same normalised sweep would span most of the
      // height and scribble over the copy; flatten it into the headline band.
      const squash = aspect < 1 ? 0.38 : 1;
      const lift = aspect < 1 ? 0.18 : 0;
      CONTROLS.forEach(([nx, ny, z], i) => {
        const wobble = motion * Math.sin(t * 0.55 + i * 1.3) * 0.05;
        pts[i][0] = nx * tanH * aspect * -z;
        pts[i][1] = ((ny + wobble) * squash + lift) * tanH * -z;
        pts[i][2] = z + motion * Math.sin(t * 0.4 + i) * 0.5;
      });
      tilt.x += ((motion ? sceneSignals.pointer.y * 0.07 : 0) - tilt.x) * 0.06;
      tilt.y += ((motion ? sceneSignals.pointer.x * 0.16 : 0) - tilt.y) * 0.06;

      const fade = Math.max(0, 1 - Math.max(0, sceneSignals.storyTime - 0.15) * 1.6);
      // Opacity on the layers, not the wrapper: a wrapper opacity would create
      // a stacking context and collapse the over/under weave.
      backG.parentElement!.style.opacity = String(fade);
      frontG.parentElement!.style.opacity = String(fade);
      const shown = reveal.current.v;
      const f = (H / 2) / tanH;

      let prevX = 0, prevY = 0, prevZ = 0;
      for (let s = 0; s < SAMPLES; s++) {
        const u = s / (SAMPLES - 1);
        catmullRom(pts, u, p);
        rotateAbout(p, tilt.x, tilt.y, CENTER_Z);
        const x = W / 2 + (p[0] / -p[2]) * f;
        const y = H / 2 - (p[1] / -p[2]) * f;
        if (s > 0) {
          const k = s - 1;
          const uMid = (s - 0.5) / (SAMPLES - 1);
          const on = uMid <= shown;
          const layer = isFront(uMid) ? "front" : "back";
          for (const name of ["back", "front"] as const) {
            const { glow, core } = layers[name][k];
            const draw = on && name === layer;
            if (!draw) {
              // Hidden segments only need hiding once.
              if (drawn[name][k]) {
                core.setAttribute("stroke-width", "0");
                glow.setAttribute("stroke-width", "0");
                drawn[name][k] = false;
              }
              continue;
            }
            drawn[name][k] = true;
            const tail = Math.min(1, uMid / 0.08, (1 - uMid) / 0.08);
            const width = (2.4 * 8) / -((p[2] + prevZ) / 2);
            const hex = lerpHex(uMid);
            for (const line of [glow, core]) {
              line.setAttribute("x1", prevX.toFixed(1));
              line.setAttribute("y1", prevY.toFixed(1));
              line.setAttribute("x2", x.toFixed(1));
              line.setAttribute("y2", y.toFixed(1));
              line.setAttribute("stroke", hex);
            }
            core.setAttribute("stroke-width", width.toFixed(2));
            glow.setAttribute("stroke-width", (width * 4.5).toFixed(2));
            core.setAttribute("stroke-opacity", (tail * 0.95).toFixed(2));
            glow.setAttribute("stroke-opacity", (tail * 0.14).toFixed(2));
          }
        }
        prevX = x; prevY = y; prevZ = p[2];
      }
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      backG.replaceChildren();
      frontG.replaceChildren();
    };
  }, []);

  return (
    <div ref={wrap} className="hero-ribbon" aria-hidden="true">
      <svg className="hero-ribbon__layer hero-ribbon__layer--back"><g ref={back} /></svg>
      <svg className="hero-ribbon__layer hero-ribbon__layer--front"><g ref={front} /></svg>
    </div>
  );
}
