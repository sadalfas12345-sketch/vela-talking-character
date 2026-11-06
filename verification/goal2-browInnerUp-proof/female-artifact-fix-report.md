# Goal 2 artifact-fix validation

Date: 2026-11-06
Branch: `wip/tripo-face-repair`

## Result

The model-agnostic quality-constrained QP is not accepted. Goal 2 remains **FAIL**.

The added local edge-strain constraints reduced the original edge-stretch mechanism in the selected brow neighborhood, but the exported female result still has a visible black triangular artifact. The reimported integrity report also records newly flipped triangles, so the solver does not yet satisfy the acceptance gate.

## Measured results

| Model | Requested brow | Achieved brow | Eyelid movement | New inversions | Visual |
|---|---:|---:|---:|---:|---|
| Female | 5.134 mm max | 5.134 mm max | 0.000 mm max | 68 at 100%, 25 at 25%, 41 at 50%, 48 at 75% | FAIL |
| Male | 27.558 mm max | 27.558 mm max | 0.000 mm max | See `male-quality-qp-integrity.json` | FAIL |

Female measured regional movement after GLB reimport is in `female-quality-qp-measurements.json`. The female artifact diagnosis reports a maximum normal change of 179.62 degrees and maximum vertex motion of 5.134 mm. The visible full-weight render is `female-quality-qp-render-final/browInnerUp_1.00.png`.

## Root cause

The confirmed defect is geometric deformation, not a material-only issue. The same artifact remains visible in the matched final render after the quality-constrained solve, and the reimported mesh has newly flipped triangles. The normal discontinuity is therefore a consequence of local surface inversion or severe nonlinear triangle deformation. The linearized orientation inequalities are not a sufficient orientation-preserving guarantee for this high-density Tripo surface.

The earlier frame test preserved donor displacement, so the anatomical frame was not the cause. Donor landmark asymmetry is present in the measured motion, but it is not enough to explain the black patch. The remaining failure is the solver's inability to guarantee nonlinear triangle orientation while preserving the full donor displacement.

## Evidence

- `female-quality-qp-render-final/browInnerUp_0.00.png`
- `female-quality-qp-render-final/browInnerUp_0.25.png`
- `female-quality-qp-render-final/browInnerUp_0.50.png`
- `female-quality-qp-render-final/browInnerUp_0.75.png`
- `female-quality-qp-render-final/browInnerUp_1.00.png`
- `female-quality-materials/clay_full.png`
- `female-quality-materials/unlit_full.png`
- `female-quality-materials/normals_full.png`
- `female-quality-artifact-diagnosis.json`
- `female-quality-qp-integrity.json`
- `male-quality-qp-integrity.json`

The material diagnostic images show the local deformation in neutral/clay/unlit/normal views; the final lit render still shows the dark triangular patch. The native Codex CLI vision command could not be executed in this Windows session because PowerShell execution policy blocked `codex.ps1`; the attached images were inspected with the available image viewer.

## Scope preserved

No Goal 1 assets, original Tripo GLBs, mouth topology, teeth, or Goal 3 work were changed. The failed candidate is retained for diagnosis. No success claim is made.
