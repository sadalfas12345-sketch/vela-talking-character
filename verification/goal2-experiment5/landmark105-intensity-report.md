# Experiment 5: Landmark 105 Folding-Intensity Diagnostic

Each tested intensity was solved independently from the original neutral patch using the existing official libigl ARAP bridge, exact barycentric landmark-105 constraint, and fixed original boundary. No target, attachment, patch, solver, or triangle correction was changed.

## Coarse intensity sweep

Folds are counted when a deformed triangle reverses orientation relative to its neutral normal. Local neighbor-normal checks were then used to distinguish a coherent triangle rotation from a genuine local fold.

| Intensity | Female folds | Male folds | Female max strain | Male max strain |
|---:|---:|---:|---:|---:|
| 0% | 0 | 0 | 0.002% | 0.002% |
| 10% | 0 | 0 | 2.245% | 8.082% |
| 20% | 0 | 0 | 5.908% | 17.222% |
| 30% | 0 | 3 | 9.415% | 24.788% |
| 40% | 0 | 3 | 12.051% | 30.955% |
| 50% | 0 | 7 | 15.406% | 36.887% |
| 60% | 0 | 9 | 20.848% | 43.290% |
| 70% | 0 | 12 | 25.583% | 50.828% |
| 80% | 0 | 31 | 30.217% | 60.623% |
| 90% | 2 | 38 | 34.796% | 64.587% |
| 100% | 2 | 41 | 39.309% | 71.289% |

The 1% refinement was executed across the full interval. First orientation-fold onset was female 83% and male 25%.

## First affected triangles

### Female, 83%

- Local triangle: 7761
- Original vertex IDs: 435201, 433401, 433077
- Neutral area: 1.44195501e-7
- Deformed area: 1.56318558e-7
- Triangle normal dot: approximately -2.74e-16
- Vertex displacement magnitudes: 0.000679407, 0.001065605, 0.000825168
- Distance from landmark 105: 0.000978708
- Edge-sharing neighbors: 7760, 7772, 8197
- Neighbor normal dots after deformation: 0.99352, 0.74427, -0.41027

The triangle area remains positive, but its relation to neighbor 8197 reverses. This is a genuine local fold, not merely a rigid triangle rotation.

### Male, 25%

The first two affected triangles are:

- Local triangle 31087, original vertex IDs 940970, 813988, 301183. Neutral area 4.67543846e-7; deformed area 4.20313723e-7; distance from landmark 105 0.000909878.
- Local triangle 31321, original vertex IDs 940970, 748962, 813988. Neutral area 3.75459082e-7; deformed area 2.93303407e-7; distance from landmark 105 0.001600912.
- Vertex displacement magnitudes for triangle 31087: 0.001448782, 0.002273670, 0.002031807.
- Neighbor normal dots for triangle 31087 change from 0.99919, 0.74642, 0.99987 to 0.50069, -0.99413, 0.97050.
- Neighbor normal dots for triangle 31321 change from 0.99987, 0.99532, 0.99979 to 0.97050, -0.13682, 0.63804.

The male fold is therefore a local fold against edge-sharing neighbors, not a smooth rotation. The first two triangles share the affected local region and become folded relative to their neighbors while their areas remain nonzero.

## Landmark accuracy and strain at onset

The exact barycentric constraint residual remained numerical zero at all intensities. At female 83% and male 25%, the reported normalized landmark errors were 0.0% to displayed precision. This confirms that the fold is caused by the surrounding deformation field, not failure to reach the landmark target.

At onset, female maximum and P95 edge strain were 31.597% and 0.590%. Male maximum and P95 edge strain were 20.533% and 0.253%.

## Evidence

- Machine-readable sweep: `verification/goal2-experiment5/landmark105-intensity/landmark105-intensity-sweep.json`
- Female onset close-up: `verification/goal2-experiment5/landmark105-intensity/female-first-fold-closeup.png`
- Male onset close-up: `verification/goal2-experiment5/landmark105-intensity/male-first-fold-closeup.png`
- Reproducible script: `scripts/run_goal2_experiment5_landmark105_intensity_sweep.py`

The snapshots and close-ups show the neutral patch beside the first-fold configuration. The original mesh and topology were not modified.
