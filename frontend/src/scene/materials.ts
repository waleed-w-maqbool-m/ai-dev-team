import * as THREE from "three";

import { COLORS } from "./stageState";

/** Matte graphite clay — every station body shares it. */
export const clay = new THREE.MeshStandardMaterial({ color: COLORS.clay, roughness: 0.85, metalness: 0.08 });
export const clayLight = new THREE.MeshStandardMaterial({ color: COLORS.clayLight, roughness: 0.78, metalness: 0.1 });

/** An unlit emissive material. Not tone-mapped, so colours pushed above 1.0
 * cross the bloom threshold and only these parts glow. */
export function emissive(color = COLORS.accent): THREE.MeshBasicMaterial {
  return new THREE.MeshBasicMaterial({ color: color.clone(), toneMapped: false });
}

const tmp = new THREE.Color();

/** Sets an emissive material to `base` scaled by `intensity`, optionally
 * mixed toward `flash` by `flashAmount`. */
export function setGlow(
  mat: THREE.MeshBasicMaterial,
  base: THREE.Color,
  intensity: number,
  flash?: THREE.Color | null,
  flashAmount = 0,
) {
  tmp.copy(base);
  if (flash && flashAmount > 0) tmp.lerp(flash, Math.min(1, flashAmount * 1.4));
  mat.color.copy(tmp).multiplyScalar(intensity);
}
