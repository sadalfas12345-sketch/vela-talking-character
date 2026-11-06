# Goal 2 controlled brow validation: orientation-constrained sparse QP

The existing sparse QP solver was retained. The remaining male defect was
isolated to five brow-surface triangles from the previous export:

| Triangle | Vertex indices | Base-space centroid |
|---:|---|---|
| 488328 | 823318, 668108, 420852 | 0.148041, -0.193992, 0.144836 |
| 490349 | 149329, 668108, 823318 | 0.149213, -0.193760, 0.145324 |
| 543991 | 803981, 591432, 700283 | 0.220419, -0.176790, 0.168411 |
| 543992 | 591432, 672379, 599306 | 0.220229, -0.176930, 0.169512 |
| 545914 | 591432, 5616, 672379 | 0.221801, -0.176143, 0.169296 |

They are clustered around the two eyebrow anchor groups. They inverted because
the prior edge-strain-only objective preserved displacement but did not constrain
the signed local triangle area. The fix adds scale-derived local signed-area
inequalities to the same QP active set. It uses no model-specific IDs, offsets,
or post-hoc vertex halving. The safety margin is 50% of each triangle's neutral
projected area, derived from that triangle itself.

## Reimported measurements

| Model | Interocular | Requested | Achieved max | Max eyelid | Inversions at 0/25/50/75/100% | Visual |
|---|---:|---:|---:|---:|---|---|
| Female | 55.843 mm | 2.792 mm | 2.843 mm | 0.0117 mm | 0 / 0 / 0 / 0 / 0 | PASS |
| Male | 299.743 mm | 14.987 mm | 15.204 mm | 0.0332 mm | 0 / 0 / 0 / 0 / 0 | PASS |

Both models exceed 90% of the prescribed movement. The male's larger absolute
movement is proportional to its measured 299.743 mm interocular distance, not
an arbitrary world-axis or fixed-size offset. The requested ratio is 5% for
both models.

There are no zero-area or collapsed triangles at any tested weight. The neutral
mesh remains unchanged at weight zero. Existing boundary/non-manifold counts
remain pre-existing and are reported separately: 55,312 female and 134,609 male.

## Evidence

- Female renders: `female-orientation-qp-render/`
- Male renders: `male-orientation-qp-render/`
- Female measurements: `female-orientation-qp-measurements.json`
- Male measurements: `male-orientation-qp-measurements.json`
- Female integrity: `female-orientation-qp-integrity.json`
- Male integrity: `male-orientation-qp-integrity.json`
- Female QP solution: `female-orientation-qp-solution.npz`
- Male QP solution: `male-orientation-qp-solution.npz`

Codex vision inspection of the exported full-weight renders shows visible,
bilateral brow elevation with stable eyes, eyelids, nose, and facial contour.
The five-weight sweeps are continuous and monotonic in the intended direction.

## Decision

The controlled Goal 2 test passes for both models. No Goal 3 work was started.
