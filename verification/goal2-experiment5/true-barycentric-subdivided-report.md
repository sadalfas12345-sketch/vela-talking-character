# Experiment 5: temporary barycentric-handle test

Command:

```powershell
python scripts/run_goal2_experiment5_subdivided_arap.py --ids 70,105 --female-patch verification/goal2-experiment5/female-128-union.patch.npz --male-patch verification/goal2-experiment5/male-128-union.patch.npz --female-goal verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --male-goal verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json --female-markers verification/goal2-browInnerUp-proof/step4-tripo-transfer/female/landmark_markers.json --male-markers verification/goal2-browInnerUp-proof/step4-tripo-transfer/male/landmark_markers.json --output verification/goal2-experiment5/true-barycentric-subdivided
```

Machine-readable output: `true-barycentric-subdivided/results-2-subdivided-arap.json`.

## Results

| Model | ID 70 source-barycentric error | ID 105 source-barycentric error | Inverted triangles | Max edge strain | Result |
|---|---:|---:|---:|---:|---|
| Female | 17.875% | 8.621% | 3 | 38.502% | FAIL |
| Male | 1.097% | 4.700% | 51 | 69.550% | FAIL |

The inserted temporary handle vertices reached their requested targets with
zero handle error on both models. This is not sufficient evidence: when the
original attachment triangle vertices are used to reconstruct the landmark,
the landmarks drift by the errors above. The handle is an independent vertex,
not the required equality

```text
wA * VA + wB * VB + wC * VC = target
```

The source vertex order and source topology were preserved. The computational
mesh added two temporary vertices and split two temporary faces only. No
original GLB was modified.

## Failure mechanism

Temporary triangle subdivision is compatible with the native fixed-vertex ARAP
API, but it does not make the inserted handle a dependent barycentric function
of the three original vertices after deformation. The original triangle can
change shape independently, so the reconstructed Goal-1 attachment no longer
equals the constrained inserted point. This is confirmed by the zero inserted
handle residual versus the nonzero source-barycentric residual.

The female also has three orientation failures and the male 51. Therefore this
adapter does not meet the two-landmark acceptance criteria even though it uses
the official ARAP implementation.

## Decision

The requested exact constraint requires an equality-constrained ARAP position
update or a solver representation in which the landmark point is dependent on
the original triangle vertices. The installed Python binding exposes neither.
The temporary-handle experiment was executed as the explicitly permitted
fallback and failed the required source-surface validation. No additional
landmarks were tested.
