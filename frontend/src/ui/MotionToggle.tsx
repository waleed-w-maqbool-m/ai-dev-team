import { useUi } from "../app/uiStore";

/** Visible override for the OS reduced-motion setting, remembered per visitor. */
export function MotionToggle() {
  const reduced = useUi((s) => s.reducedMotion);
  const set = useUi((s) => s.setReducedMotion);
  return (
    <button type="button" className="motion-toggle" aria-pressed={reduced} onClick={() => set(!reduced)}>
      <span className="motion-toggle__box" aria-hidden="true" />
      Reduce motion
    </button>
  );
}
