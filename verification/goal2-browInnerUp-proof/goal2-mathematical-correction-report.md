# Goal 2 mathematical correction audit

## Scope

This report records the corrected embedding-frame test, the replacement of the pseudo-bending term with a dihedral-angle energy, the nonlinear equilibrium experiment, and the controlled female and male runs. The legacy orientation-constrained QP remains unchanged as the comparison baseline.

## Confirmed mathematical corrections

- Render embedding now treats cached local frames as row-vector frames. The map is `o' = o (B0.T B1)`. A synthetic 90 degree triangle rotation transports an off-surface offset from `[0.2, 0.3, 0.1]` to `[-0.3, 0.2, 0.1]` exactly.
- Bending is computed from the signed dihedral angle of adjacent triangles, not opposite-vertex pseudo-springs. The neutral finite-difference gradient is below `4e-13` on the synthetic hinged surface.
- Equilibrium uses sparse PyTorch autograd with strong-Wolfe LBFGS and reports the final gradient norm. It is not fixed-step force relaxation.
- Frontalis fibers with zero rest length are excluded. A superior insertion anchor is derived from the brow-region centroid and fiber endpoints, without model-specific coordinates or vertex IDs.

## Embedding audit

The cached embedding contains extrapolating barycentric weights. Female: 5,313 of 135,183 valid physics embeddings. Male: 40,871 of 481,671. This is a confirmed preprocessing defect and prevents claiming anatomically valid render embedding. It must be corrected before Goal 2 can pass.

## Solver results

| Model | Target mean | Achieved at 100% | Gradient residual | Minimum physics area ratio | Visual | Export/reimport |
|---|---:|---:|---:|---:|---|---|
| Female | 1.332 mm | 0.340 mm | 0.0410 | 0.253 | FAIL | FAIL |
| Male | 8.819 mm | 0.478 mm | 1.6645 | 0.464 | FAIL | FAIL |

The requested donor displacement was not reached. The solver saturated at the shared contraction bound of `0.1`; this is an inverse-calibration failure, not a reason to weaken the acceptance threshold.

## Export integrity

The exported female GLB has 291,813 winding flips at full weight, 8 zero-area triangles, 10 collapsed triangles, and 52,591 boundary or non-manifold edges reported after reimport. The male GLB has 32 winding flips at full weight and 134,609 boundary or non-manifold edges. Weight sweeps were evaluated at 0, 25, 50, 75, and 100 percent. The female render visibly contains severe triangular shading and geometry artifacts; the male render is visually intact at a glance but does not show the required brow motion and fails geometric integrity.

## Files

- Synthetic math tests: `anatomical-math-synthetic-tests.json`
- Female solver log: `female-torch-anatomical-solution.json`
- Male solver log: `male-torch-anatomical-solution.json`
- Female export integrity: `female-torch-integrity.json`
- Male export integrity: `male-torch-integrity.json`
- Female weight renders: `female-torch-render/`
- Male weight renders: `male-torch-render/`

## Determination

Goal 2 remains **FAILED**. The corrected mathematics found real defects, but the current anatomy graph and render embedding are not yet suitable for a passing expression transfer. No Goal 3 work was started.
