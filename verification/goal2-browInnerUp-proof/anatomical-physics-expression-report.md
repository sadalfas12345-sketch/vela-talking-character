# Goal 2 anatomical physics expression report

## Result

Goal 2 **FAILS**. The new mechanical path runs on the same preprocessing rules for both characters and exports/reimports valid morph-bearing GLBs, but it does not produce a convincing brow raise and does not satisfy geometry quality on the female and male exports.

## Physics and activation

The solver uses vector stretch springs, opposite-vertex bending springs derived from adjacent physics triangles, soft anatomical anchors, and contractile frontalis fibers whose rest lengths shorten with activation. Donor calibration is normalized by target interocular width.

Shared activation calibration:

- Normalized donor motion ratio: 0.02386135
- Frontalis contraction ratio: 0.01193068
- Tested activations: 0, .25, .5, .75, 1

| Model | Physics nodes | Springs | Bend pairs | Frontalis fibers | Runtime | Brow movement | Eyelid movement | Inversions | Visual |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Female | 7,229 | 16,766 | 12,085 | 2,006 | 16.4 s | 0.0037 mm max | 0 mm | 2 at 100% | FAIL |
| Male | 9,416 | 18,168 | 10,350 | 2,695 | 41.7 s | 0.1444 mm max | 0.1681 mm max | 2 at 100% | FAIL |

The female equilibrium also reached a minimum physics triangle-area ratio of approximately 0.015 at several intermediate/full activations, indicating severe local collapse even though most areas remained positive.

## Root causes

1. Frontalis fibers were generated, but their contraction does not produce the required landmark-scale brow motion through the current coarse network. Female brow movement after export is effectively zero.
2. The male embedding transfers motion into eyelid and eye landmarks, showing that the current region classification and coarse-triangle embedding are not yet anatomically reliable under deformation.
3. The current nonlinear relaxation has no complete collision/contact model and only rejects negative physics triangle areas. Positive-but-nearly-collapsed triangles and render-level inversions remain possible.
4. Neutral reconstruction is exact by construction, but that does not validate the deformed embedding.

## Evidence

- Female render sweep: `female-anatomical-render/`
- Male render sweep: `male-anatomical-render/`
- Female measurements: `female-anatomical-measurements.json`
- Male measurements: `male-anatomical-measurements.json`
- Female integrity: `female-anatomical-integrity.json`
- Male integrity: `male-anatomical-integrity.json`
- Physics runtime logs: `female-anatomical-solution.json`, `male-anatomical-solution.json`

The original render mesh and experimental QP baseline remain preserved. No Goal 1, mouth, teeth, or Goal 3 work was changed.
