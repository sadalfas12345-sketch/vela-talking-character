# Goal 2 Experiment 4: Real Landmark 70

This experiment used the existing Goal-1 landmark 70 records and existing transferred marker trajectory. No landmark coordinates or source meshes were changed. The constraint was applied through the original triangle's barycentric weights, then measured again from that same triangle after official libigl ARAP.

| Model | Triangle vertex IDs | Barycentric weights | Requested magnitude | Achieved magnitude | Error | Max neighbor movement | New inversions | Collapses | Result |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Female | 480918, 481139, 481619 | 0.198131, 0.494774, 0.307096 | 0.001196547 | 0.001196547 | 9.36e-14 | 0.001545310 | 0 | 0 | PASS |
| Male | 144461, 645786, 795958 | 0.243646, 0.019730, 0.736624 | 0.006422602 | 0.006422602 | 6.11e-15 | 0.006069606 | 5 | 0 | FAIL |

The female patch had 4,340 vertices and 8,387 triangles. The male patch had 31,845 vertices and 62,878 triangles in the final retry. Runtimes were 1.282 seconds female and 10.270 seconds male.

## Failure and one correction

The initial 128-hop patch reached the male landmark target exactly but produced 6 inverted triangles. One shared correction was made by enlarging the connected patch to 256 edge hops. The female remained valid, but the male still produced 5 inverted triangles. The blocker remains geometric integrity under the existing male landmark-70 target. The requested displacement was not reduced and the solver was not changed.

## Visual observation

The close-up overlays show the existing landmark-70 neutral point in blue, transferred target in yellow, and achieved barycentric point in red. The solved point matches the target numerically. The overlay also makes the existing camera-space placement issue visible: the female point appears at the left brow or hair boundary rather than clearly inside the brow skin. This is not corrected here because the experiment forbids changing Goal-1 attachments.

## Decision

Experiment 4 FAILED on the male due to 5 new inverted triangles after the permitted patch enlargement. The exact next blocker is the incompatibility between the existing male landmark-70 barycentric target and zero-inversion ARAP deformation on this connected surface. Stop here; do not proceed to Experiment 5.
