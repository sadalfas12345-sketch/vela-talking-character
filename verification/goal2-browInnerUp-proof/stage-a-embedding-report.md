# Goal 2 Stage A: physics-to-render transfer

## Scope

Stage A was run without muscle activation, donor calibration, spring optimization, or equilibrium solving. The only active operation was a prescribed smooth forehead displacement on the coarse physics surface followed by physics-to-render embedding.

## Confirmed defects fixed

1. The builder discarded the BVH nearest hit and computed barycentrics from the original off-surface render point. It now computes barycentrics from the actual closest surface hit.
2. The barycentric calculation now uses closest-point region tests, avoiding numerical extrapolation on skinny triangles.
3. The embedding offset transport now uses the affine map between the neutral and deformed coarse triangle frames. This is the correct row-vector map for translation, rotation, and in-plane scale.

## Attachment results

| Model | Valid attachments | Extrapolating weights | Neutral reconstruction error | Duplicate skin groups | Max seam motion disagreement |
|---|---:|---:|---:|---:|---:|
| Female | 122,220 | 0 | 5.42e-20 | 4,683 | 1.14e-10 |
| Male | 963,028 | 0 | 2.17e-19 | 40,189 | 0 |

The prior extrapolation counts were caused by the discarded BVH hit and ill-conditioned barycentric evaluation. The corrected attachment stage eliminates them without clamping weights.

## Synthetic validation

The corrected affine frame map passes the 90-degree triangle rotation test exactly: an off-surface offset `[0.2, 0.3, 0.1]` maps to `[-0.3, 0.2, 0.1]`. The existing dihedral finite-difference test also passes with neutral gradient norm `3.43e-13`.

Evidence: `anatomical-math-synthetic-tests.json`.

## Controlled real-model deformation

A normalized smooth Gaussian forehead displacement was applied directly to the physics nodes at weights 0, 25, 50, 75, and 100 percent.

Female controlled displacement at 100 percent was 3.428 mm on the physics surface and 3.410 mm maximum on the render surface. Male values were 15.258 mm and 15.255 mm. Motion was monotonic in both models and neutral displacement was below `3.3e-16`.

However, exported render integrity still fails:

| Model | 25% flips | 50% flips | 75% flips | 100% flips | Zero/collapsed triangles at 100% | Visual result |
|---|---:|---:|---:|---:|---:|---|
| Female | 34 | 115 | 186 | 234 | 0 / 0 | FAIL |
| Male | 9 | 26 | 44 | 54 | 0 / 0 | FAIL |

The controlled renders show no detached coarse attachments, but the triangle flips demonstrate that the per-triangle affine offset transport is still discontinuous or incompatible with the original high-resolution detail near the deformed region. Therefore the embedding stage cannot yet be accepted.

## Evidence

- Female controlled measurements: `female-controlled-embedding-fixed.json`
- Male controlled measurements: `male-controlled-embedding-fixed.json`
- Female integrity: `female-controlled-integrity.json`
- Male integrity: `male-controlled-integrity.json`
- Female renders: `female-controlled-render/`
- Male renders: `male-controlled-render/`

## Decision

**Stage A: FAILED.**

The attachment extrapolation bug is fixed, but the original render mesh does not yet follow the coarse surface with zero new inversions. Stage B and Stage C were not started.
