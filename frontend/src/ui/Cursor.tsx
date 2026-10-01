// Dot + damped ring that morphs into a label over actions (data-cursor="RUN").
// Only on fine pointers with hover; touch and keyboard users keep the native
// behaviour, and text fields keep the text cursor.
import gsap from "gsap";
import { useEffect, useRef, useState } from "react";

export function Cursor() {
  const root = useRef<HTMLDivElement>(null);
  const dot = useRef<HTMLDivElement>(null);
  const ring = useRef<HTMLDivElement>(null);
  const [enabled] = useState(() => window.matchMedia("(hover: hover) and (pointer: fine)").matches);
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !dot.current || !ring.current || !root.current) return;
    // Not "data-cursor": that attribute names an action label, and <html>
    // would then match closest("[data-cursor]") everywhere on the page.
    document.documentElement.dataset.cursorMode = "custom";
    const dx = gsap.quickTo(dot.current, "x", { duration: 0.08, ease: "power3.out" });
    const dy = gsap.quickTo(dot.current, "y", { duration: 0.08, ease: "power3.out" });
    const rx = gsap.quickTo(ring.current, "x", { duration: 0.3, ease: "power3.out" });
    const ry = gsap.quickTo(ring.current, "y", { duration: 0.3, ease: "power3.out" });
    const el = root.current;

    const move = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      dx(e.clientX); dy(e.clientY); rx(e.clientX); ry(e.clientY);
      delete el.dataset.hidden;
      const target = (e.target as HTMLElement | null)?.closest<HTMLElement>("[data-cursor]");
      setLabel(target?.dataset.cursor ?? null);
    };
    const leave = () => (el.dataset.hidden = "");
    window.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    return () => {
      window.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
      delete document.documentElement.dataset.cursorMode;
    };
  }, [enabled]);

  if (!enabled) return null;
  return (
    <div ref={root} className="cursor" data-label={label ?? undefined} data-hidden="" aria-hidden="true">
      <div ref={ring} className="cursor__ring">
        <span className="cursor__label">{label}</span>
      </div>
      <div ref={dot} className="cursor__dot" />
    </div>
  );
}
