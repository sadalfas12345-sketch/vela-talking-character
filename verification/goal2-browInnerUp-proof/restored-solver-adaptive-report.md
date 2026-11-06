# Goal 2 restored-solver validation

## Status

Goal 2 remains **FAIL**. The orientation-constrained solver from `eab30f95` was restored. Its original real-motion outputs have zero triangle inversions at weights 0, .25, .5, .75, and 1, but the female dark brow artifact remains.

## Baseline diagnosis

Female original restored output:

- Maximum brow motion: 5.312 mm.
- Maximum normal change: 16.737 degrees.
- Maximum local edge stretch: 1.513x.
- Triangle inversions: 0 at every tested weight.

The artifact is therefore not a winding inversion. It remains visible in clay and unlit material diagnostics, indicating a geometric gap or sharp displacement discontinuity rather than a texture-only or lighting-only artifact.

## Adaptive surface backoff

The same model-agnostic procedure backtracks the broad restored displacement field until nonlinear local edge ratios remain between .80x and 1.25x and sampled triangle signed areas remain positive.

| Model | Adaptive scale | Requested brow | Achieved brow | Eyelid movement | Inversions at all weights | Visual |
|---|---:|---:|---:|---:|---:|---|
| Female | 0.311635 | 5.134 mm | 1.656 mm max | 0.00196 mm max | 0 | FAIL |
| Male | 0.334950 | 27.558 mm | 9.096 mm max | 0.00053 mm max | 0 | FAIL |

The adaptive field is geometrically stable after export and reimport, but the motion is too attenuated and the female render still contains a visible crease/gap near the brow. It does not meet the requested natural visible expression acceptance.

## Evidence

- Restored baseline integrity: `female-restored-orientation-integrity.json`
- Restored baseline artifact diagnosis: `female-restored-artifact-diagnosis.json`
- Adaptive scale reports: `female-adaptive-report.json`, `male-adaptive-report.json`
- Adaptive integrity: `female-adaptive-integrity.json`, `male-adaptive-integrity.json`
- Adaptive measurements: `female-adaptive-measurements.json`, `male-adaptive-measurements.json`
- Adaptive renders: `female-adaptive-render/`, `male-adaptive-render/`
- Material diagnostics: `female-adaptive-materials/`

No Goal 1, mouth, teeth, or Goal 3 work was performed.
