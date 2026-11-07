# Goal 2 Experiment 1: Move the Skin

This is a controlled libigl ARAP surface-patch experiment. It does not modify the source GLBs, Goal 1 attachments, or landmark trajectories.

The patch is extracted from the original connected mesh around existing landmark 336. The final run uses the same 16-edge-hop extraction rule on both models. Two stationary vertices and one moved vertex are selected geometrically from each patch. The moved vertex is prescribed an upward displacement equal to 1% of that model's existing Goal 1 interocular distance, using the existing target anatomical up axis.

| Model | Patch vertices | Patch triangles | Eye width | Requested | Achieved | Ratio | Max neighbor | New inversions | Collapses | Visual evidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Female | 160 | 266 | 0.0558429 | 0.000558429 | 0.000558429 | 100.000% | 0.000547963 | 0 | 0 | `female-before-after-overlay.png` |
| Male | 286 | 484 | 0.299743 | 0.002997431 | 0.002997431 | 100.000% | 0.002788836 | 0 | 0 | `male-before-after-overlay.png` |

Neighbor movement acceptance is 10% of requested movement. Both models exceed it. The final runs produced zero inverted and zero collapsed triangles.

## Initial failure and one correction

The first 8-edge-hop patch produced one male inverted triangle. The moving vertex reached its target, but the local support was too small for that mesh's face scale and topology. One shared correction was made: increase the connected patch radius to 16 edge hops for both models. No displacement threshold, solver, or character-specific factor was changed.

The corrected run used the official libigl `arap_precomputation` and `arap_solve` API. The images are textured neutral renders with the neutral patch edges in blue and the solved moved vertex in red. They are diagnostic overlays of actual solved vertex positions, not a claim that the full render mesh was baked.

## Result

Experiment 1 passes its stated controlled criteria on both original Tripo characters. This does not establish full-face expression transfer.
