import { useEffect, type RefObject } from "react";
import type * as THREE from "three";

const skip = () => {};

/** Excludes a decorative subtree from pointer raycasts. Invisible lines are
 * still raycast by three.js (with a generous 1-unit line threshold), which
 * would otherwise steal hovers from the stations behind them. */
export function useNoRaycast(ref: RefObject<THREE.Object3D | null>) {
  useEffect(() => {
    ref.current?.traverse((o) => {
      o.raycast = skip;
    });
  });
}
