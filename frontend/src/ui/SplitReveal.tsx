// Headline reveal: lines rise from behind a mask (expo.out, 0.08s line
// stagger), optionally triggered on scroll. Uses GSAP SplitText (re-splits on
// resize); screen readers read an untouched sr-only copy of the text.
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { useRef, type ReactNode } from "react";

import { useUi } from "../app/uiStore";

gsap.registerPlugin(SplitText, ScrollTrigger, useGSAP);

interface Props {
  as?: "div" | "span" | "p" | "h1" | "h2" | "h3";
  className?: string;
  children: ReactNode;
  /** Reveal when scrolled into view instead of immediately. */
  onScroll?: boolean;
  delay?: number;
  /** Split into characters too (for short emphasised phrases). */
  chars?: boolean;
  /** Re-run the reveal whenever this changes (e.g. a new caption). */
  replayKey?: unknown;
  id?: string;
}

export function SplitReveal({ as = "div", className, children, onScroll, delay = 0, chars, replayKey, id }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const Tag = as as "div"; // one concrete tag type keeps the JSX typing simple
  const reduced = useUi((s) => s.reducedMotion);
  const ready = useUi((s) => s.sceneReady);

  useGSAP(
    () => {
      const el = ref.current;
      if (!el || !ready) return;
      if (reduced) {
        gsap.set(el, { autoAlpha: 1 });
        return;
      }
      const split = SplitText.create(el, {
        type: chars ? "lines,chars" : "lines",
        mask: "lines",
        linesClass: "split-line",
        aria: "none", // screen readers get the sr-only copy below instead
        autoSplit: true,
        onSplit(self) {
          gsap.set(el, { autoAlpha: 1 });
          const targets = chars ? self.chars : self.lines;
          return gsap.from(targets, {
            yPercent: 110,
            duration: chars ? 0.9 : 1.15,
            ease: "expo.out",
            stagger: chars ? 0.035 : 0.08,
            delay,
            scrollTrigger: onScroll ? { trigger: el, start: "top 85%", once: true } : undefined,
          });
        },
      });
      return () => split.revert();
    },
    { dependencies: [reduced, ready, replayKey], scope: ref, revertOnUpdate: true },
  );

  // The semantic element keeps a plain-text copy for assistive tech; the
  // visible copy is split into animated line wrappers and hidden from it.
  // (SplitText's own aria mode puts aria-label on spans, which axe rejects.)
  return (
    <Tag className={className} id={id}>
      <span className="sr-only">{children}</span>
      <span ref={ref} className="split-target" aria-hidden="true" style={{ visibility: reduced ? "visible" : "hidden" }}>
        {children}
      </span>
    </Tag>
  );
}
