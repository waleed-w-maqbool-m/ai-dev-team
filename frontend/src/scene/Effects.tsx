import { Bloom, EffectComposer, Noise, Vignette } from "@react-three/postprocessing";

import { useUi } from "../app/uiStore";

/** Restrained finish: bloom only on emissive parts (they're the only colours
 * above 1.0), light grain, vignette. Tier 1 drops bloom; tier 0 drops it all. */
export function Effects() {
  const tier = useUi((s) => s.perfTier);
  if (tier === 0) return null;
  if (tier === 1) {
    return (
      <EffectComposer multisampling={0} enableNormalPass={false}>
        <Noise opacity={0.035} />
        <Vignette offset={0.3} darkness={0.55} />
      </EffectComposer>
    );
  }
  return (
    <EffectComposer multisampling={0} enableNormalPass={false}>
      <Bloom mipmapBlur luminanceThreshold={0.9} luminanceSmoothing={0.15} intensity={0.8} radius={0.72} />
      <Noise opacity={0.035} />
      <Vignette offset={0.3} darkness={0.55} />
    </EffectComposer>
  );
}
