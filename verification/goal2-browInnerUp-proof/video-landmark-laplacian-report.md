# Goal 2 — Landmark motion to surface deformation

## Result: FAILED

The existing Step-4 landmark trajectories were consumed without recalculating video motion, normalization, or correspondence. The first female surface bake used Blender 5.2.3's built-in `LAPLACIANDEFORM` modifier on a proxy made from original Tripo triangles.

The bake is not accepted because Blender repeatedly reported `The system did not find a solution` for the Tripo proxy components. The exported file therefore does not demonstrate a valid Laplacian surface deformation.

## Inputs

- Female source: `assets/tripo/vela-photoreal/generated-rigged.glb`
- Female Goal-1 attachments: `verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json`
- Female existing motion controls: `verification/goal2-browInnerUp-proof/step4-tripo-transfer/female/landmark_markers.json`
- New implementation: `scripts/bake_goal2_landmark_laplacian_deform.py`

## Modifier diagnostics

- Original target vertices: 999,787
- Local original-surface proxy vertices: 43,717
- Proxy triangles: 84,313
- Connected control components solved independently: 10
- Proxy degenerate triangles discarded: 0
- Proxy duplicate triangles discarded: 0
- Blender modifier: `LAPLACIANDEFORM`, 30 iterations
- Required Goal-1 attachments: 468/468
- Barycentric control system rank: 25/25
- Pre-modifier barycentric residual: <=1.74e-18
- Blender solver status: FAILED for the Tripo-derived components

The synthetic Blender 5.2 grid test passed with the same bind and anchor workflow, so this is an input-topology or modifier-system compatibility failure, not an untested API path.

## Exported integrity

The exported female GLB was reimported and measured at all weights:

| Weight | Winding flips | Zero-area | Collapsed |
|---:|---:|---:|---:|
| 0% | 0 | 0 | 0 |
| 25% | 29 | 0 | 0 |
| 50% | 64 | 0 | 0 |
| 75% | 84 | 0 | 0 |
| 100% | 97 | 0 | 0 |

The imported mesh also reports 55,312 boundary/nonmanifold edges. These results fail geometric validity.

## Visual evidence

- [Female neutral render](female-video-landmark-laplacian-neutral.png)
- [Female 100% render](female-video-landmark-laplacian-100.png)

Visual inspection: FAIL. The 100% render shows little or no convincing eyebrow surface motion and visible triangular/crease artifacts around the forehead and eyelid region.

## Scope decision

The male bake was not launched after the shared implementation failed on the first model. No deformation, Goal-1, mouth, or video-motion code was changed. The generated GLB is retained locally as failed evidence and is not committed as a production asset.

## Next blocker

The original Tripo surface must be made compatible with Blender's Laplacian system in a solver-only representation that preserves a deterministic mapping back to the original vertices. This requires an explicit topology diagnostic and repair of the proxy's solver connectivity before testing both characters.
