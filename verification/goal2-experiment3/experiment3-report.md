# Goal 2 Experiment 3: Different Skin Movements

Official libigl ARAP was reused with the Experiment 2 control-selection rule. Every moving control received a deterministic vector from one shared pattern: inner forehead upward 1% of eye width, outer forehead upward 0.5%, smooth interpolation between them, and a horizontal component bounded by 0.2% of eye width. The two Experiment 2 stationary boundary controls were retained for each model.

| Moving controls | Female | Male | Max control error | New inversions |
|---:|---|---|---:|---:|
| 2 | PASS | PASS | 1.47e-13 / 1.60e-14 | 0 / 0 |
| 4 | PASS | PASS | 1.53e-13 / 1.60e-14 | 0 / 0 |
| 8 | PASS | PASS | 1.61e-13 / 6.76e-15 | 0 / 0 |
| 16 | PASS | PASS | 1.61e-13 / 1.60e-14 | 0 / 0 |

The error values are maximum relative 3D vector errors for female and male respectively. All tests had zero collapsed triangles, finite coordinates, and neighbor movement above the required 10% of the maximum requested displacement.

## Final patch and runtime

| Model | Patch vertices | Patch triangles | 16-control runtime | 16-control max neighbor movement | Maximum requested distance |
|---|---:|---:|---:|---:|---:|
| Female | 2,156 | 4,118 | 0.571 s | 0.000550068 | 0.000542882 |
| Male | 10,675 | 20,776 | 3.047 s | 0.002908534 | 0.002969818 |

## Corrections after failures

The initial 32-edge-hop patch failed male at 2 controls with 1 inverted triangle. Control accuracy and neighbor motion passed. The shared patch was enlarged to 64 edge hops, which fixed the 2-control case but produced 1 inversion for male at 8 controls. The shared patch was enlarged to 128 edge hops. The final 128-hop patch passed 2, 4, 8, and 16 controls on both models. Requested vectors and thresholds were never reduced or relaxed.

## Evidence

- `female-16-control-directional-before-after.png`
- `male-16-control-directional-before-after.png`

The images show textured neutral renders with blue neutral patch edges and red/yellow solved control positions and movement arrows. Source GLBs and neutral geometry were not modified.

## Result

Experiment 3 passed all requested control counts on both original Tripo characters using one libigl ARAP implementation and one deterministic displacement rule.
