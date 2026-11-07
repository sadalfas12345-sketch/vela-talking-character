# Experiment 5 stop report: landmarks 70 and 105

This is the first required control set. The experiment stopped here and did not test four or six landmarks.

## Test configuration

- Solver: official libigl `arap_precomputation` and `arap_solve`
- Controls: MediaPipe landmarks 70 and 105
- Target: existing neutral-to-peak trajectories
- Patch: deterministic union of 16-edge-hop neighborhoods around the two Goal-1 attachment triangles
- Constraints: barycentric landmark constraints converted to minimum-norm vertex constraints, with the patch boundary stationary
- Fold handling: existing automatic shared-edge correction
- Source geometry: unchanged

## Results

| Model | Landmark 70 error | Landmark 105 error | New inverted triangles | Collapses | Maximum edge strain | Result |
|---|---:|---:|---:|---:|---:|---|
| Female | 0.595% | 23.140% | 7 | 0 | 83.82% | FAIL |
| Male | approximately 0% | approximately 0% | 28 | 0 | 351.37% | FAIL |

The requested landmark vectors and achieved vectors are in `results-2.json`.

## Failure diagnosis

The failure occurs before the four- and six-landmark tests:

1. The female 70/105 constraints are not reproduced simultaneously. Landmark 105 misses its target by 23.14%, exceeding the 5% limit.
2. The male constraints reach their barycentric targets, but the small union patch develops 28 orientation failures and extreme local strain.
3. The automatic local-fold correction does not make this control set valid. It is a geometric safeguard, not a replacement for a compatible multi-control deformation support.

The confirmed immediate mechanism is an under-supported multi-control patch: two independently moving barycentric triangles are constrained while the outer patch boundary is held fixed. The resulting minimum-norm vertex constraints create incompatible local gradients, producing either target error or damaged geometry. No four- or six-landmark attempt was made.

## Reproducibility

```powershell
python scripts/extract_goal2_experiment5_multi_patch.py --source <GLB> --goal1 <Goal1 report> --output <patch.json> --landmark-ids 70,105 --hop-radius 16
python scripts/run_goal2_experiment5_libigl.py --ids 70,105 ...
```

Machine-readable result: `results-2.json`.

Experiment 5 is stopped pending a targeted correction to the multi-control support construction. No Goal 1 data, source GLBs, or ARAP solver were changed.
