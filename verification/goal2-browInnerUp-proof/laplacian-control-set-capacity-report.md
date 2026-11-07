# Goal 2 — Native Laplacian Control-Set Capacity

Branch: `wip/tripo-face-repair`  
Previous baseline: `27c8b84fc80ab6ce34f9ec7575fa11afd353aa00`

This diagnostic consumed the existing Goal-1 attachments and transferred 100% brow-expression marker targets. It did not re-track video, rebuild correspondence, alter either GLB, or use another deformation solver.

## Commands

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/diagnose_goal2_laplacian_control_sets.py -- --source assets/tripo/vela-photoreal/generated-rigged.glb --goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --markers verification/goal2-browInnerUp-proof/step4-tripo-transfer/female/landmark_markers.json --output verification/goal2-browInnerUp-proof/control-sets-female-corrected.json

& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/diagnose_goal2_laplacian_control_sets.py -- --source assets/tripo/generalization-male-20261105/generated-original.glb --goal1 verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json --markers verification/goal2-browInnerUp-proof/step4-tripo-transfer/male/landmark_markers.json --output verification/goal2-browInnerUp-proof/control-sets-male-corrected.json
```

Raw results:

- [Female control-set JSON](control-sets-female-corrected.json)
- [Male control-set JSON](control-sets-male-corrected.json)
- [Diagnostic script](../../scripts/diagnose_goal2_laplacian_control_sets.py)

## Step 1 — real expression targets

**Result: PASS, 15/15.**

Both existing marker manifests supplied 468 required IDs, with 468/468 valid Goal-1 attachments. The manifests also contain 478 total records, so the required canonical 0–467 set is complete and the extra 468–477 entries were not used.

The target data were read directly from the existing `100` sample. No displacement was attenuated or regenerated. The same canonical control ordering and automatic connected-component grouping were used for both models.

Measured model metadata:

| Model | Mesh vertices | Local proxy vertices | Proxy triangles | Required attachments | Interocular width |
|---|---:|---:|---:|---:|---:|
| Female | 999,787 | 78,517 | 149,749 | 468/468 | 0.05584288581 |
| Male | 991,219 | 839,802 | 1,601,904 | 468/468 | 0.29974311045 |

The control candidates were selected from the existing brow, eyelid, forehead and actually moving landmark trajectories. Each candidate was required to have its full Goal-1 attachment triangle inside the tested connected component.

## Step 2 — control-set sweep

The requested sizes were tested as independent landmark counts: 3, 6, 12, 24, 48, plus all relevant controls available in each component. The actual mesh-anchor count is reported separately because one barycentric landmark generally expands to three or more mesh anchor vertices.

### Female

Ten relevant connected components were tested. Every tested set bound, but every one evaluated with zero free-vertex movement.

Representative component 30, which was the prior minimal failure:

| Independent controls | Actual mesh anchors | Bind | Free max | P95 landmark error | Native result |
|---:|---:|---|---:|---:|---|
| 3 | 12 | true | 0 | 6.22e-7 | no free motion |
| 6 | 21 | true | 0 | 1.11e-6 | no free motion |
| 12 | 21 | true | 0 | 1.11e-6 | no free motion |
| 24 | 21 | true | 0 | 1.11e-6 | no free motion |
| 48 | 21 | true | 0 | 1.11e-6 | no free motion |
| all relevant | 21 | true | 0 | 1.11e-6 | no free motion |

The same zero-free-motion result occurred on components 1, 12, 14, 20, 28, 31, 35, 39, 43 and 47. Blender repeatedly emitted `The system did not find a solution` during these evaluations.

### Male

Twenty-nine relevant connected components were tested. Many produced free motion, but this did not establish a usable facial control set. Landmark fidelity was below the required 95% on representative components, and triangle inversion/collapse metrics were not collected by this diagnostic harness.

Representative results:

| Component | Independent controls | Actual anchors | Free motion | P95 landmark error | Result |
|---:|---:|---:|---:|---:|---|
| 21 | 3 | 12 | 0.0271357 | 0.00319181 | free motion, fidelity not accepted |
| 21 | 12 | 39 | 0.0209199 | 0.00653566 | free motion, fidelity not accepted |
| 32 | 3 | 12 | 0.0335022 | 0.00337425 | free motion, fidelity not accepted |
| 32 | 12 | 39 | 0.0566548 | 0.0101046 | free motion, fidelity not accepted |
| 32 | 48 | 147 | 0.0355227 | 0.00758741 | free motion, fidelity not accepted |
| 297 | 12 | 38 | 0.0118771 | 0.00418608 | free motion, fidelity not accepted |
| 330 | 6 | 17 | 0.0336968 | 0.00427092 | free motion, fidelity not accepted |

Across the male tested configurations, achieved/requested maximum-motion ratios ranged from approximately 0.507 to 0.994. The highest ratio alone is insufficient: it does not certify all meaningful landmarks, triangle integrity, or visual expression quality.

### Measurement completeness

Recorded for every tested configuration:

- independent landmark count;
- actual mesh-anchor count;
- barycentric solve rank and residual;
- native bind result;
- native evaluation status;
- maximum and RMS free-vertex motion;
- requested and achieved motion maxima;
- median and P95 landmark error.

Not recorded in this harness:

- per-configuration triangle inversion and collapse counts;
- runtime and peak memory;
- rendered visual evidence.

Those omissions are not treated as passing measurements.

## Stop decision

Step 2 did not establish a usable control set on both characters:

- Female: **FAIL** — all real control-set sizes produced zero free-surface motion.
- Male: **FAIL for acceptance** — free motion occurred, but fidelity was not consistently at least 95%, and geometry integrity was not measured.

Under the requested stop rule, Steps 3, 4 and 5 were not run. No maximum reliable control set is claimed, no five-weight validation was performed, and no renders or GLB bakes were produced.

The evidence supports this conclusion: native Laplacian behavior depends not only on control count, but on how barycentric landmark controls expand into mesh anchors and how those anchors interact with each connected component. Three free-moving anchors from the prior synthetic diagnostic are not equivalent to three real facial landmark controls.

## Scorecard

| Step | Score | Result |
|---|---:|---|
| Step 1: real expression targets | 15/15 | PASS |
| Step 2: control-set experiments | 20/30 | FAIL — diagnostic executed, but triangle-quality and runtime/memory measurements were not recorded and no common usable set was found |
| Step 3: maximum reliable control set | 0/20 | NOT RUN |
| Step 4: both-character validation | 0/25 | NOT RUN |
| Step 5: evidence and decision | 0/10 | NOT RUN |
| **Total** | **35/100** | **FAILED** |

`BLENDER LAPLACIAN: NOT YET VIABLE`

`OVERALL STEP RESULT: FAILED`
