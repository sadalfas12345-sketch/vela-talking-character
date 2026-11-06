# Goal 2 direct original-render-mesh test

This experiment bypasses the coarse physics mesh, springs, muscle activation, donor transfer, and equilibrium solver. It applies one normalized smooth forehead displacement directly to the original Tripo render vertices.

## Method

- Brow anchors: Goal1 landmarks `70, 63, 105, 336, 293, 334`.
- Up direction: normalized eye midpoint minus chin.
- Influence: Gaussian distance from the brow anchors, normalized by interocular distance, with a continuous upper-face falloff.
- Coincident vertices: grouped by world position and assigned identical displacement.
- Backtracking: amplitude halved until all tested weights had zero winding flips and zero collapsed triangles.
- Shape key: `direct_browInnerUp_test` on the original imported mesh.

## Results

| Model | Interocular width | Requested | Safe amplitude | Weighted achieved motion | New inversions | Collapsed triangles | Reimport |
|---|---:|---:|---:|---:|---:|---:|---|
| Female | 55.843 mm | 1.000 mm | 0.250 mm | 0.114 mm | 0 | 0 | PASS |
| Male | 299.743 mm | 1.000 mm | 0.500 mm | 0.217 mm | 0 | 0 | PASS |

All tested weights 0, 25, 50, 75, and 100 percent had zero new winding flips, zero zero-area triangles, and zero collapsed triangles after GLB reimport. Vertex and triangle counts were preserved. The integrity tool reports pre-existing nonmanifold or boundary edges in the source assets, but no new deformation-induced topology damage.

## Visual result

The neutral and raised renders preserve the character appearance without visible cracks. The raised brows are too subtle to qualify as a convincing approximately 1 mm brow raise, especially on the female. The safe direct field therefore does not meet the requested expression target.

Evidence:

- Female report: `female-direct-brow.json`
- Male report: `male-direct-brow.json`
- Female integrity: `female-direct-brow-integrity.json`
- Male integrity: `male-direct-brow-integrity.json`
- Female renders: `female-direct-render/`
- Male renders: `male-direct-render/`

## Decision

**Direct original-mesh experiment: FAILED for the requested visible 1 mm expression.**

It demonstrates a stable small deformation path, but it does not provide enough eyebrow motion to proceed as a working Goal2 solution.
