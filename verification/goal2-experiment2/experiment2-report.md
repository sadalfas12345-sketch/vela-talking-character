# Goal 2 Experiment 2: Multiple Skin Vertices

Official libigl ARAP was reused without changing the solver or landmark pipeline. Each model used its existing connected forehead patch around landmark 336, two stationary anchors, and automatically selected moving controls using deterministic farthest-point sampling. Every moving control received the same upward displacement equal to 1% of that model's interocular width.

| Moving controls | Female | Male | Female max control error | Male max control error | Female inversions | Male inversions |
|---:|---|---|---:|---:|---:|---:|
| 2 | PASS | PASS | 5.42e-14 | 1.33e-15 | 0 | 0 |
| 4 | PASS | PASS | 5.55e-14 | 1.33e-15 | 0 | 0 |
| 8 | PASS | PASS | 5.55e-14 | 1.33e-15 | 0 | 0 |
| 16 | PASS | PASS | 5.55e-14 | 1.33e-15 | 0 | 0 |

All control errors are relative displacement error. All configurations also had zero collapsed triangles.

## Patch and runtime measurements

| Model | Patch vertices | Patch triangles | Requested displacement | Max neighbor at 16 controls | Runtime at 16 controls |
|---|---:|---:|---:|---:|---:|
| Female | 443 | 784 | 0.000558429 | 0.000600350 | 0.0992 s |
| Male | 1,142 | 2,117 | 0.002997431 | 0.003039915 | 0.2922 s |

The 16-control neighbor ratios were 1.075 female and 1.014 male, above the required 0.10 threshold.

## Targeted correction

The initial 16-edge-hop patch failed at the first 2-control test on the male with one inverted triangle. The controls themselves reached 100% and neighboring vertices moved, so the failure was local patch support. One shared correction was made: enlarge the connected patch from 16 to 32 edge hops for both models. The requested movement and thresholds were unchanged. The corrected 2-control test passed on both models, after which 4, 8, and 16 were executed.

## Evidence

- `female-16-control-before-after.png`
- `male-16-control-before-after.png`

These are textured neutral renders with the actual solved 16-control positions overlaid. Blue lines show the neutral patch and red/yellow marks show the solved control movement. No source GLB or neutral mesh was modified.

## Result

Experiment 2 passed all four control counts on both characters using one implementation and automatic selection rules.
