// A button that leans up to 8px toward the cursor and springs back, with an
// orange (or ink) fill sweeping in from the side the cursor entered.
import gsap from "gsap";
import { useEffect, useRef, type AnchorHTMLAttributes, type ButtonHTMLAttributes, type ReactNode } from "react";

import { useUi } from "../app/uiStore";

type Common = { children: ReactNode; variant?: "primary" | "ghost"; size?: "md" | "sm"; cursor?: string };
type AsButton = Common & ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined };
type AsLink = Common & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string };

const MAX_PULL = 8;

function useMagnet<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const reduced = useUi((s) => s.reducedMotion);
  useEffect(() => {
    const el = ref.current;
    if (!el || reduced || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const x = gsap.quickTo(el, "x", { duration: 0.5, ease: "power3.out" });
    const y = gsap.quickTo(el, "y", { duration: 0.5, ease: "power3.out" });
    const enter = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--fill-from", e.clientX < r.left + r.width / 2 ? "left" : "right");
    };
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const nx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
      const ny = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
      x(gsap.utils.clamp(-1, 1, nx) * MAX_PULL);
      y(gsap.utils.clamp(-1, 1, ny) * MAX_PULL);
    };
    const leave = () => {
      gsap.to(el, { x: 0, y: 0, duration: 0.7, ease: "elastic.out(1, 0.45)" });
    };
    el.addEventListener("pointerenter", enter);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    return () => {
      el.removeEventListener("pointerenter", enter);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
      gsap.set(el, { x: 0, y: 0 });
    };
  }, [reduced]);
  return ref;
}

export function MagneticButton(props: AsButton | AsLink) {
  const { children, variant = "primary", size = "md", cursor, className = "", ...rest } = props;
  const cls = `btn btn--${variant} ${size === "sm" ? "btn--sm" : ""} ${className}`;
  const linkRef = useMagnet<HTMLAnchorElement>();
  const buttonRef = useMagnet<HTMLButtonElement>();
  const inner = (
    <>
      <span className="btn__fill" aria-hidden="true" />
      {children}
    </>
  );
  if ("href" in rest && rest.href !== undefined) {
    return (
      <a ref={linkRef} className={cls} data-cursor={cursor} {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)}>
        {inner}
      </a>
    );
  }
  return (
    <button ref={buttonRef} className={cls} data-cursor={cursor} {...(rest as ButtonHTMLAttributes<HTMLButtonElement>)}>
      {inner}
    </button>
  );
}
