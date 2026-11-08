# Topology-independent facial deformation test

Test case: original landmark 105 neutral-to-peak movement from the existing Experiment 5 data. Original female and male GLBs were not modified.

## Experiment A — RBF

The test used an exact thin-plate RBF interpolant with an affine tail. The landmark-105 barycentric point was the moving control and automatically sampled boundary points from the connected landmark-105 patch were stationary controls. The field was evaluated directly on original render vertices.

| Measurement | Female | Male |
|---|---:|---:|
| Requested movement | 0.00152390 | 0.00817973 |
| Landmark target error | 0.00000928, 0.609% | 0.00003097, 0.379% |
| Foldovers | 0 | 0 |
| Collapsed triangles | 0 | 0 |
| Maximum edge strain | 13.49% | 46.58% |
| P95 edge strain | 6.17% | 14.91% |
| Minimum area ratio | 0.901 | 0.572 |
| Runtime | 19.57 s | 18.47 s |
| Self-intersections | Not tested exhaustively | Not tested exhaustively |
| Visual result | FAIL | FAIL |

The numerical landmark and orientation checks alone were insufficient. The female render showed severe spike-like deformation. The male render also showed unacceptable local distortion under the full target. RBF therefore failed the visual and deformation-quality requirements.

Evidence:

- [Female neutral render](female-render/neutral-textured.png)
- [Female RBF render](female-render/deformed-textured.png)
- [Male neutral render](male-render/neutral-textured.png)
- [Male RBF render](male-render/deformed-textured.png)
- [Female RBF report](female-rbf.json)
- [Male RBF report](male-rbf.json)

## Experiment B — Blender Mesh Deform cage

Blender's native `MESH_DEFORM` modifier bound successfully to automatically generated closed box cages around the connected facial patches. The control test then translated the cage by the full landmark target to test whether native cage deformation could reproduce the landmark motion.

| Measurement | Female | Male |
|---|---:|---:|
| Bind | Success | Success |
| Landmark target error | 0.93411, 61,297% | 0.00818, 100% |
| Foldovers | 0 measured | 0 measured |
| Collapsed triangles | 0 measured | 0 measured |
| Runtime | 8.28 s | 8.09 s |
| Visual result | FAIL | FAIL |

Binding success did not produce the required landmark movement. The female readback was numerically invalid for the target and the male patch did not move. This fallback therefore fails the acceptance criteria.

Evidence:

- [Female Mesh Deform report](female-mesh-deform.json)
- [Male Mesh Deform report](male-mesh-deform.json)

## Conclusion

Neither tested topology-independent method passed on both original Tripo models at full landmark-105 movement. The original meshes remain preserved and are still the source assets.

FEMALE: FAIL  
MALE: FAIL  
OVERALL STEP RESULT: FAILED
