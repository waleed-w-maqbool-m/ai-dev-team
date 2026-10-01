// 000 → 100 (reference: Lusion). The count tracks real milestones — fonts,
// the 3D bundle, the first rendered frame — so it never lies about loading.
import gsap from "gsap";
import { useEffect, useRef, useState } from "react";

import { useUi } from "./uiStore";

export function Preloader({ progress }: { progress: number }) {
  const [gone, setGone] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const count = useRef<HTMLSpanElement>(null);
  const bar = useRef<HTMLDivElement>(null);
  const shown = useRef({ v: 0 });
  const reduced = useUi((s) => s.reducedMotion);

  useEffect(() => {
    const tween = gsap.to(shown.current, {
      v: progress,
      duration: reduced ? 0 : 0.9,
      ease: "power2.out",
      onUpdate: () => {
        if (count.current) count.current.textContent = String(Math.round(shown.current.v)).padStart(3, "0");
        if (bar.current) bar.current.style.transform = `scaleX(${shown.current.v / 100})`;
      },
      onComplete: () => {
        if (progress < 100 || !root.current) return;
        gsap.to(root.current, {
          yPercent: -100,
          duration: reduced ? 0 : 1.1,
          ease: "expo.inOut",
          delay: reduced ? 0 : 0.15,
          onComplete: () => setGone(true),
        });
      },
    });
    return () => {
      tween.kill();
    };
  }, [progress, reduced]);

  if (gone) return null;
  return (
    <div ref={root} className="preloader" role="status" aria-label="Loading">
      <span ref={count} className="preloader__count" aria-hidden="true">000</span>
      <p className="mono dim preloader__meta">Assembling the team · five agents, one line</p>
      <div ref={bar} className="preloader__bar" aria-hidden="true" />
    </div>
  );
}
