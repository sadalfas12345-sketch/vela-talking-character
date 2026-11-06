# Goal 2 mathematical root-cause audit

## Baseline formulation

For each extracted local vertex `i`, the restored solver uses a world-space displacement `d_i`. For every local edge `(u,v)` with neutral length `L_uv`, the implemented objective is:

`min Σ ||(d_u - d_v) / L_uv||² + 1e-4 Σ ||d_i||²`

The barycentric landmark matrix `A` is assembled from the stored triangle vertex indices and barycentric weights. The hard constraints are:

`A d_x = desired_x`, `A d_y = desired_y`, and `A d_z = desired_z`.

The active orientation rows are first-order signed-area constraints. For neutral triangle normal `n̂` and vertices `p0,p1,p2`, the solver constrains the linearized area expression to at least `0.5 q0`, where `q0 = n̂ · ((p1-p0) × (p2-p0))`. Vertices outside the extracted submesh have implicit zero displacement. There is no explicit displacement-continuity halo at the local boundary.

The KKT system is the standard equality-constrained quadratic system:

`[H Cᵀ; C 0] [d λ] = [0 b]`

where `H = DᵀD + 1e-4 I`, `C` contains the three coordinate copies of `A` plus active orientation rows.

## Confirmed defects

1. The local graph is not a single connected surface graph. The female problem has 39 connected components and the male problem has 433.

2. The mesh contains coincident duplicate vertices that are independent unknowns. Female: 2,574 coincident groups, maximum displacement disagreement 5.122 mm. Male: 21,632 groups, maximum disagreement 23.788 mm. This directly permits a visible seam across a UV/material/primitive split even when the KKT residual is small.

3. The local boundary is implicitly fixed at zero with no halo. The objective penalizes edge differences only for edges retained in the extracted graph. It does not penalize the displacement jump between a moved local component and a coincident or adjacent vertex outside that graph.

4. Zero winding flips are insufficient. The restored female baseline has zero flips but local edge ratios from 0.387 to 1.519 and a 16.737° maximum normal change. The male baseline ranges from 0.451 to 1.760. The orientation inequalities constrain only first-order signed area, not nonlinear strain, curvature, or duplicate-vertex continuity.

5. The barycentric constraints are not rank-deficient: both selected problems have rank 25 with minimum singular values about 0.578 female and 0.579 male. Their maximum residual is about 6e-12. Therefore the artifact is not caused by an inconsistent landmark matrix or a failed KKT solve.

## Correction experiment

Tying coincident duplicate vertices with equality constraints reduced female duplicate displacement disagreement from 5.122 mm to 7.75e-11 mm. However, with the original hard donor constraints, it produced 22 female winding flips at 100%. That proves the duplicate split is a real defect, but also proves that tying it alone is not a sufficient correction. The experiment is retained in `female-continuity-*` artifacts and is not accepted as the production solver.

## Minimal synthetic interpretation

Two coincident copies of a surface vertex with independent displacement unknowns produce a discontinuity whenever one copy is constrained and the other is not. The edge objective cannot remove that discontinuity if the copies are in different graph components or have no connecting edge. A KKT residual of zero only proves that the selected equations were satisfied; it does not prove continuity of the geometric quotient mesh. This reproduces the exact mechanism measured in the Tripo data.

## Conclusion

The confirmed mathematical root cause is missing continuity constraints across coincident duplicate vertices and disconnected local graph components, compounded by a zero-displacement local boundary. The restored solver remains the baseline. No production correction is claimed because the first continuity correction conflicts with the hard donor constraints and reintroduces inversions. Goal 2 remains FAIL.
