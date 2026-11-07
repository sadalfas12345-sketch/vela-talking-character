# Goal 2 Experiment 4: Real Landmark 70

This experiment used the existing Goal-1 landmark 70 records and existing transferred marker trajectory. No landmark coordinates or source meshes were changed. The constraint was applied through the original triangle's barycentric weights, then measured again from that same triangle after official libigl ARAP.

| Model | Triangle vertex IDs | Barycentric weights | Requested magnitude | Achieved magnitude | Error | Max neighbor movement | New inversions | Collapses | Result |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Female | 480918, 481139, 481619 | 0.198131, 0.494774, 0.307096 | 0.001196547 | 0.001196547 | 9.36e-14 | 0.001545310 | 0 | 0 | PASS |
| Male | 144461, 645786, 795958 | 0.243646, 0.019730, 0.736624 | 0.006422602 | 0.006422602 | 6.11e-15 | 0.006069606 | 5 | 0 | FAIL |

The female patch had 4,340 vertices and 8,387 triangles. The male patch had 31,845 vertices and 62,878 triangles in the final retry. Runtimes were 1.247 seconds female and 10.219 seconds male after the support correction.

## Five-triangle diagnosis

The initial 128-hop male solve reached the target exactly but produced 6 inverted triangles. The 256-hop baseline produced these five local triangle IDs: `28820, 28827, 28839, 28840, 29125`.

Their original mesh vertex IDs were:

- `28820`: `649592, 317854, 795958`, neutral area `1.171336e-6`, deformed area `1.625612e-6`
- `28827`: `356310, 649592, 795958`, neutral area `1.735039e-6`, deformed area `2.035556e-6`
- `28839`: `645786, 657177, 407009`, neutral area `1.249680e-6`, deformed area `2.081332e-6`
- `28840`: `645786, 364169, 657177`, neutral area `1.561050e-6`, deformed area `2.498089e-6`
- `29125`: `645786, 669053, 364169`, neutral area `1.425132e-6`, deformed area `1.699237e-6`

The triangles cluster within `0.00107` to `0.00284` mesh units of landmark 70 and share edges in two local pairs. They are not boundary triangles. This confirms the failure is concentrated near the three-vertex barycentric control, not caused by the outer patch boundary.

## Targeted correction and result

The one targeted correction changed only the temporary constraint construction: a connected one-ring support around the landmark triangle received the same target vector, while the original barycentric landmark was still measured from its original triangle and weights. The female remained valid. The male inversion count fell from five to one, but did not reach zero. The remaining post-correction inverted local triangle is `11505`, with original vertices `300778, 80827, 674898`.

## Visual observation

The close-up overlays show the existing landmark-70 neutral point in blue, transferred target in yellow, and achieved barycentric point in red. The solved point matches the target numerically. The overlay also makes the existing camera-space placement issue visible: the female point appears at the left brow or hair boundary rather than clearly inside the brow skin. This is not corrected here because the experiment forbids changing Goal-1 attachments.

## Decision

Experiment 4 FAILED on the male because one new inverted triangle remains after the targeted support correction. The exact blocker is the existing male landmark-70 target combined with the local surface geometry under this ARAP constraint construction. Stop here; do not proceed to Experiment 5.
