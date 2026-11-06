# Goal 2 controlled brow test: sparse constrained QP

## Scope

This is a controlled 5% interocular eyebrow displacement test on the original
female and unrigged male Tripo meshes. It replaces the prior 24-iteration
Gaussian smoothing followed by vertex-halving. The QP uses the imported mesh's
local facial subgraph, normalized edge-strain regularization, exact brow and
stable-anatomy equality constraints, and a sparse KKT solve. No character-
specific vertex IDs or offsets are used.

The original neutral mesh is preserved at zero influence. The exported GLBs
were reimported before all measurements.

## Results

| Model | Eye width | Requested brow | Achieved brow | Eyelid movement | New inversions | Visual | GLB reimport |
|---|---:|---:|---:|---:|---:|---|---|
| Female | 55.843 mm | 2.792 mm | 2.843 mm max | 0.0117 mm max | 0 | PASS for controlled geometry | PASS |
| Male | 299.743 mm | 14.987 mm | 15.396 mm max | 0.0310 mm max | 5 | FAIL | PASS, integrity FAIL |

The reported displacement is measured from Goal 1 barycentric anatomical
attachments after GLB export and reimport, using spatial matching to the
reimported neutral surface rather than assuming vertex indices survived.

Female brow-anchor measurements are 2.792, 2.792, 2.691, 2.843, 2.830,
and 2.804 mm. Male measurements are 15.337, 15.396, 14.987, 14.987, 14.987,
and 14.987 mm. Both exceed 90% of the prescribed displacement.

## Integrity by weight

| Model | 0.00 | 0.25 | 0.50 | 0.75 | 1.00 |
|---|---:|---:|---:|---:|---:|
| Female winding flips | 0 | 0 | 0 | 0 | 0 |
| Male winding flips | 0 | 0 | 1 | 2 | 5 |

There were no zero-area or collapsed triangles at any tested weight. The male
failure is therefore not caused by the old post-hoc halving stage: it appears
inside the constrained QP deformation field as the weight increases, while
the hard eyebrow constraints remain satisfied. The current optimizer's
edge-strain objective does not sufficiently protect the five local male
triangles from orientation inversion. It must not be accepted as a production
solver yet.

The existing GLBs have pre-existing boundary/non-manifold edge counts of
55,312 female and 134,609 male; these are reported separately and were not
counted as newly introduced inversions.

## Visual and continuous-weight evidence

The five-weight reimported render sweeps are:

- Female: `female-controlled-qp-render/sweep/`
- Male: `male-controlled-qp-render/sweep/`

The rendered 0, 0.25, 0.50, 0.75, and 1.00 states show continuous brow motion.
The female visibly raises both brows without an obvious eyelid or nose change.
The male brow movement is visible, but the geometry integrity failure prevents
a PASS claim even though eyelid displacement is small.

## Failure decision

The sparse constrained QP fixes the measured constraint-attenuation defect and
passes the displacement and eyelid targets on both meshes. Goal 2 remains
FAILED because the male has five newly inverted triangles, beginning at 0.50
weight and increasing to five at full weight. No Goal 3 work was started.

Evidence:

- Female measurements: `female-controlled-qp-measurements.json`
- Male measurements: `male-controlled-qp-measurements.json`
- Female integrity: `female-controlled-qp-integrity.json`
- Male integrity: `male-controlled-qp-integrity.json`
- Female bake: `female-controlled-qp-bake.json`
- Male bake: `male-controlled-qp-bake.json`
