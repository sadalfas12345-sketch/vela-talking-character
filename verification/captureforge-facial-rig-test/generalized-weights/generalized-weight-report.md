# Generalized CaptureForge facial skinning audit

Branch: `wip/tripo-face-repair`  
Baseline: `7ca023d`

## Scope

This experiment replaced CaptureForge's localized Euclidean falloff weights with a shared, connectivity-aware surface weighting method. The existing 26-bone rig architecture, original GLBs, Goal 1 mappings, and stored full landmark-105 target were preserved. No video coefficients were replayed and no independent cheek or jaw control was tested because the eyebrow regression did not pass on both characters.

Command:

```text
blender -b --python scripts/generalize_captureforge_surface_weights.py
```

## Existing weighting diagnosis

CaptureForge's `captureforge/face/autofit.py::skin_weights` computes each anchored bone's influence from Euclidean distance:

```text
d_i = ||v_i - anchor_b||
w_raw(i,b) = smoothstep(1 - d_i / radius_b)^2
```

It then normalizes overlapping weights and assigns the remainder to `head`. If a radius misses the mesh, it falls back to at most 32 nearest vertices. This creates compact, independently localized control islands. It does not account for face-surface connectivity, geodesic distance, intervening anatomical regions, or continuity between adjacent controls. The brow controls therefore receive strong weights only in small neighborhoods, which explains the previously observed concentrated deformation.

## Generalized method tested

`scripts/generalize_captureforge_surface_weights.py` uses one shared procedure for both models:

1. Map Goal 1 surface points to the exact original target GLB, including the measured female source-to-target translation.
2. Derive the facial region from automatically mapped anatomical controls and `3.0 * interocular_width`.
3. Build a triangle-edge graph over that region using actual 3D edge lengths.
4. Use multi-source Dijkstra distances from each bone's nearest 16 surface vertices.
5. Convert geodesic distance to a smooth falloff with support `max(3 * original_radius, 1.5 * interocular_width)`.
6. Normalize overlapping influences and assign the residual to `head`.
7. Rebind the unchanged CaptureForge 26-bone architecture.

This is a generalized connectivity-aware weight distribution, not a landmark-105 or character-specific patch.

## Results

| Measurement | Female | Male |
|---|---:|---:|
| Goal 1 landmarks mapped | 478 | 478 |
| Median surface mapping distance | 3.401e-7 | 1.560e-7 |
| Interocular width | 0.05584185 | 0.29974317 |
| Graph-region vertices | 101,443 | 437,678 |
| Graph-region triangles | 195,008 | 828,237 |
| `brow.mid.R` nonzero weights | 2,453 | 8,441 |
| Requested landmark-105 displacement | 0.00152390 model units | 0.00817973 model units |
| Achieved landmark-105 displacement | 77.618% | 98.507% |
| Landmark-105 error | 22.382% | 1.493% |
| Minimum triangle area ratio | 0.8342 | 0.7976 |
| Collapsed triangles | 0 | 0 |
| Maximum edge strain | 11.582% | 10.533% |
| P95 edge strain | 2.574e-7% | 1.400e-7% |
| Visual eyebrow result | FAIL | FAIL |

The displacement percentages above are computed from actual evaluated mesh coordinates at the original landmark-105 barycentric attachment, not from the bone transform or a marker target.

The generalized field reduced the prior direct-translation maximum edge strain from 37.93% to 11.58% on the female and from 40.56% to 10.53% on the male. This improvement does not compensate for the female target-fidelity failure or the visual-quality failure.

## Root cause of this experiment's failure

The new graph field blends neighboring brow controls. On the female, the target landmark's original `brow.mid.R` translation is no longer transmitted nearly one-to-one through its local surface weights: the evaluated barycentric landmark receives only 77.618% of the requested displacement. This is a consequence of normalized overlapping geodesic influences, not a missing attachment or an armature-evaluation failure.

The male has a larger and denser graph region, and its local normalized influence happens to transmit 98.507% of the same control translation. That is not sufficient evidence of a robust shared solution because the female fails the same acceptance test and the actual male render does not show a convincing natural eyebrow raise.

## Visual inspection

The neutral and full-target textured renders were inspected directly:

- Female: the full-target render shows only a subtle localized/uneven brow change; it does not establish a convincing natural raise of the eyebrow region.
- Male: the full-target render shows the intended localized control response, but not a clearly convincing smooth eyebrow raise across the surrounding forehead.
- Neither inspected pair showed a new gross crack, spike, or catastrophic collapse in the rendered view. Numerical integrity also reports zero collapsed triangles, but this does not satisfy the visual-expression requirement.

Evidence:

- Female [neutral](female/neutral.png) and [full target](female/full-target.png)
- Male [neutral](male/neutral.png) and [full target](male/full-target.png)
- Female [measurements](female/result.json)
- Male [measurements](male/result.json)
- Reproducible implementation: [generalize_captureforge_surface_weights.py](../../../scripts/generalize_captureforge_surface_weights.py)

## Decision

Generalized weight generation: **FAIL**  
Female full-target eyebrow deformation: **FAIL**  
Male full-target eyebrow deformation: **FAIL**  
Independent facial-control generalization: **NOT TESTED**

The process stopped at the required gate. No cheek or jaw experiment was run, and no further correction was attempted after identifying the female attenuation mechanism.

OVERALL STEP RESULT: **FAILED**
