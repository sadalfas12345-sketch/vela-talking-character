# Experiment 4: last skin-fold correction

Baseline ARAP result: `23b96b247c082c8d9b6e55108b5e9b9fe017fcb5`

The official libigl ARAP solve and landmark-70 target were preserved. The correction is a local, automatically detected shared-edge orientation correction. It moves only the minimum amount required to restore the original side relationship of an edge-sharing triangle pair. It does not delete triangles, reverse winding, reduce the target, or change the neutral mesh.

## Feasibility

A valid solution exists. For the male fold, the problematic pair is triangle 11505 and neighbor 11501. At full expression, moving the offending opposite vertex across the shared-edge plane requires approximately `0.000971` model units in the minimal correction. The landmark-70 triangle is separate, so its barycentric target remains unchanged.

## Results across the motion path

Samples: 0%, 25%, 50%, 65%, 68.9846%, 70%, 75%, and 100%.

| Model | Candidate fold pairs | Max landmark error | New genuine folds | Collapses | Minimum area ratio | Maximum edge strain | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| Female | 0 | `1.86e-13` | 0 | 0 | 0.7013 | 27.94% | PASS |
| Male | 1 | `6.11e-15` | 0 | 0 | 0.4785 | 48.80% | PASS |

The male correction activates only at the fold transition and remains continuous through the tested intensities. At 100%, its maximum correction relative to the original ARAP surface is `0.0009709` model units. The female requires no correction.

At every tested intensity:

- The barycentric landmark-70 error is below 5%.
- No genuine shared-edge fold remains.
- No newly collapsed triangles occur.
- All coordinates remain finite.
- The original neutral geometry and topology are unchanged.

## Evidence

- [Original fold diagnosis](triangle11505-verification-report.md)
- [Corrected numerical report](local-fold-correction-report.md)
- [Machine-readable results](local-fold-correction-report.json)
- [Triangle and neighbor close-up](male-triangle11505-neighbors.png)
- [Female correction overlay](female-triangle-fold-correction-overlay.png)
- [Original female before/after](female-landmark70-before-after.png)
- [Original male before/after](male-landmark70-before-after.png)

Commands:

```powershell
python scripts/correct_goal2_experiment4_local_fold.py
python scripts/render_goal2_experiment4_fold_correction_overlay.py
```

No GLB export or Experiment 5 was started.
