# Experiment 5: landmarks 70 and 105 stop report

The restored Experiment 4 baseline was preserved. To include landmark 105, the test used deterministic 128-hop union patches around the existing 70 and 105 Goal-1 triangles. Both constraints were solved together in one libigl ARAP system using barycentric attachments. No independent deformation results were added.

## Results

| Model | Landmark 70 error | Landmark 105 error | New orientation failures | Collapses | Maximum edge strain | Result |
|---|---:|---:|---:|---:|---:|---|
| Female | 2.07% | 22.48% | 11 | 0 | 61.96% | FAIL |
| Male | 9.62% | 0.35% | 21 | 0 | 324.58% | FAIL |

Patch sizes:

- Female: 8,689 vertices and 16,728 triangles.
- Male: 24,126 vertices and 47,155 triangles.

The existing automatic fold correction was applied. It did not make the two-control result valid.

## Blocker

Adding landmark 105 changes the control system from the successful single-landmark one-ring construction to a coupled two-landmark barycentric system. With the available connected union patches and fixed boundaries, the ARAP solution produces incompatible local gradients:

- Female cannot reproduce landmark 105 within 5%.
- Male cannot reproduce landmark 70 within 5%.
- Both produce substantial local orientation failures.

This is a confirmed two-landmark control-support failure, not a video or Goal-1 mapping change.

No four- or six-landmark tests were run. No solver, source GLB, or Goal-1 attachment was modified.

Machine-readable result: `two-landmark-baseline-extension/results-2.json`.

