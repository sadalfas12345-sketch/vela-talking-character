# Experiment 5 Case A stop report

Case A moved landmark 70 alone on the same 128-hop union patch intended for the A/B/C comparison.

## Results

| Model | Landmark 70 error | New inversion count | Collapses | Maximum edge strain | Result |
|---|---:|---:|---:|---:|---|
| Female | `9.35e-14` | 0 | 0 | 30.14% | PASS |
| Male | `4.32e-15` | 5 | 0 | 28.76% | FAIL |

Patch sizes:

- Female: 8,689 vertices and 16,728 triangles.
- Male: 24,126 vertices and 47,155 triangles.

## Correction tested

The first Case A attempt constrained only landmark-70 triangle vertices and failed both models. The one targeted correction restored Experiment 4's validated one-ring support controls for the single-landmark baseline while keeping the 128-hop patch and stationary boundary unchanged.

That correction restored landmark accuracy and female geometry. It did not eliminate the five male geometry failures. No further correction or control set was attempted.

The current result is therefore insufficient to establish the requested A/B/C comparison. Cases B and C were not run.

Machine-readable results:

- `case-a/results-1.json`
- `case-a-corrected/results-1.json`

Reproducible command:

```powershell
python scripts/run_goal2_experiment5_libigl.py --ids 70 --female-patch verification/goal2-experiment5/female-128-union.patch.npz --male-patch verification/goal2-experiment5/male-128-union.patch.npz --female-goal verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --male-goal verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json --female-markers verification/goal2-browInnerUp-proof/step4-tripo-transfer/female/landmark_markers.json --male-markers verification/goal2-browInnerUp-proof/step4-tripo-transfer/male/landmark_markers.json --output verification/goal2-experiment5/case-a-corrected
```

