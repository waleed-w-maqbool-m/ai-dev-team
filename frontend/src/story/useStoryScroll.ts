// Lenis smooth scroll (synced to ScrollTrigger on GSAP's ticker) and the
// mapping from scroll position to "story time" (0..5), which drives the 3D
// camera and the DOM captions alike.
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { useEffect, useState, type RefObject } from "react";

import { sceneSignals, useUi } from "../app/uiStore";

gsap.registerPlugin(ScrollTrigger);

export interface StorySections {
  hero: RefObject<HTMLElement | null>;
  team: RefObject<HTMLElement | null>;
  line: RefObject<HTMLElement | null>;
  proof: RefObject<HTMLElement | null>;
  enter: RefObject<HTMLElement | null>;
}

/** Scroll lengths of the pinned sections, in viewport heights. */
export const TEAM_PIN = 4.2;
export const LINE_PIN = 4.4;

export function useStoryScroll(sections: StorySections): number {
  const reduced = useUi((s) => s.reducedMotion);
  const ready = useUi((s) => s.sceneReady);
  const [storyTime, setStoryTime] = useState(0);

  useEffect(() => {
    if (!ready) return;
    let lenis: Lenis | null = null;
    let tick: ((time: number) => void) | null = null;
    if (!reduced) {
      lenis = new Lenis({ lerp: 0.085, smoothWheel: true });
      lenis.on("scroll", ScrollTrigger.update);
      tick = (time) => lenis!.raf(time * 1000);
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);
    }

    const el = (r: RefObject<HTMLElement | null>) => r.current!;
    const vh = () => window.innerHeight;
    const triggers = [
      ScrollTrigger.create({ trigger: el(sections.hero), start: "top top", end: "bottom top" }),
      ScrollTrigger.create({ trigger: el(sections.team), start: "top top", end: () => `+=${vh() * TEAM_PIN}`, pin: true, anticipatePin: 1 }),
      ScrollTrigger.create({ trigger: el(sections.line), start: "top top", end: () => `+=${vh() * LINE_PIN}`, pin: true, anticipatePin: 1 }),
      ScrollTrigger.create({ trigger: el(sections.proof), start: "top top", end: "bottom bottom" }),
      ScrollTrigger.create({ trigger: el(sections.enter), start: "top bottom", end: "bottom bottom" }),
    ];

    // One mapping from scroll to story time, so sections never overlap.
    let last = -1;
    const update = () => {
      const y = window.scrollY;
      let t = 0;
      triggers.forEach((st, i) => {
        if (y >= st.start) t = i + Math.min(1, (y - st.start) / Math.max(1, st.end - st.start));
      });
      sceneSignals.storyTime = t;
      // React only needs coarse updates (captions change a handful of times).
      const coarse = Math.round(t * 200) / 200;
      if (coarse !== last) {
        last = coarse;
        setStoryTime(coarse);
      }
    };
    const st = ScrollTrigger.create({ start: 0, end: "max", onUpdate: update, onRefresh: update });
    update();

    // Fonts change line lengths and therefore section heights.
    document.fonts?.ready.then(() => ScrollTrigger.refresh());

    return () => {
      st.kill();
      triggers.forEach((t) => t.kill());
      if (tick) gsap.ticker.remove(tick);
      lenis?.destroy();
      sceneSignals.storyTime = 0;
    };
  }, [ready, reduced, sections]);

  return storyTime;
}
