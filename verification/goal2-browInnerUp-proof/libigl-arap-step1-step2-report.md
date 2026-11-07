# libigl ARAP validation — Step 1 and Step 2

Branch: `wip/tripo-face-repair`  
Previous transfer commit: `90bfcb69364315c49beb27c630ba45e242366133`  
Previous native Laplacian result: `7a24f57`

The official `libigl` Python binding was installed as package version 2.6.3. The test used `igl.arap_precomputation` and `igl.arap_solve` on the original Tripo-derived component coordinates and connectivity. No source GLB was modified.

## Step 1 — official ARAP on real Tripo components

Extraction command:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/extract_goal2_arap_components.py -- --source assets/tripo/vela-photoreal/generated-rigged.glb --goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --output verification/goal2-browInnerUp-proof/arap-step1-extraction.json
```

ARAP command:

```powershell
py -3 scripts/test_goal2_libigl_arap_components.py --output verification/goal2-browInnerUp-proof/arap-step1-results.json
```

| Component | Vertices | Triangles | Requested handle | Achieved handle | Ratio | Free max | Free RMS | Inversions | Collapses | Min area ratio | Runtime |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | 1,152 | 2,122 | 0.000473989757 | 0.000473989757 | 100.000% | 0.000354259550 | 0.000268807385 | 0 | 0 | 0.997806 | 0.286 s |
| 1 | 5,385 | 10,413 | 0.000949022705 | 0.000949022705 | 100.000% | 0.000621906710 | 0.000148042521 | 0 | 0 | 0.996431 | 1.567 s |

The handle displacement was 1% of each component bounding-box diagonal. Two handles were stationary and one was moved. Both components produced nonzero free-vertex movement, no new inverted triangles, and no collapsed triangles. Peak RSS deltas were approximately 2.9 MB and 7.0 MB respectively.

**Step 1: PASS, 20/20.**

## Step 2 — barycentric landmark adapter precondition

Before subdividing triangles, the original Goal-1 attachment triangles were checked against the exact extracted component vertex sets. The selected anatomical controls were brow landmarks 70, 63, 105, 336, 293, 334 and eyelid landmarks 159, 145, 386, 374.

Audit command:

```powershell
py -3 scripts/audit_goal2_arap_barycentric_adapter.py --goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --directory verification/goal2-browInnerUp-proof --output verification/goal2-browInnerUp-proof/arap-step2-adapter-audit.json
```

Actual result:

| Component | Fully represented selected controls | Partial or boundary controls | Adapter status |
|---:|---:|---:|---|
| 30 | 0/10 | 10/10 outside the extracted component | NOT READY |
| 1 | 0/10 | 10/10 outside the extracted component | NOT READY |

None of the ten selected brow/eyelid attachment triangles is contained in either extracted component. All ten attachment triangles lie outside these isolated component vertex sets. Component 30 does contain six other complete landmark triangles, but they are IDs 31, 117, 127, 130, 226 and 247, not the brow/eyelid controls required for this expression. Component 1 contains 79 complete triangles, but none of the ten selected brow/eyelid controls.

This means a temporary subdivision adapter cannot represent the requested anatomical controls on these isolated component meshes while preserving their original triangle context. Subdividing only the in-component portion would change the attachment triangle and would not preserve the original barycentric landmark definition. Including the missing triangle vertices would expand the computational component and is outside the requested Step-2 test on the existing isolated components.

**Step 2: FAIL, 0/25.** The failure is an attachment/component-boundary limitation, not an ARAP convergence failure. No ARAP landmark solve was attempted after this precondition failed.

## Stop decision

Per the requested gate, Steps 3–5 were not run. No eyebrow deformation, GLB export, reimport, or visual render is claimed.

Recommended next experiment: construct a larger computational region that includes every original triangle needed by the selected barycentric attachments, while preserving an explicit mapping to the original render mesh. This requires authorization because it is no longer the two isolated component test specified here.

## Scorecard

STEP 1: 20/20 PASS  
STEP 2: 0/25 FAIL  
STEP 3: 0/25 NOT RUN  
STEP 4: 0/20 NOT RUN  
STEP 5: 0/10 NOT RUN  

TOTAL SCORE: 20/100  
OVERALL STEP RESULT: FAILED
