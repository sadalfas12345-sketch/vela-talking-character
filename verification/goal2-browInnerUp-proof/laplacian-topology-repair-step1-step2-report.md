# Goal 2 — Laplacian solver topology repair

## Stopped after Step 2

The required stop condition was reached: Step 2 found no intervention that changes the native Blender Laplacian result from solver evaluation failure to valid free-surface deformation. Steps 3–5 were not run.

## Step 1 — Isolate the failed component

**20/20 — PASS.** The existing local proxy was split by its original mesh connectivity and each control-containing component was tested with Blender 5.2.3's native `LAPLACIANDEFORM` bind and a small controlled anchor displacement.

Smallest reproducible failing component:

- Component: 30
- Vertices: 1,152
- Triangles: 2,122
- Connected components inside test: 1
- Open boundary edges: 180
- Nonmanifold edges with more than two incident triangles: 0
- Zero-area triangles: 0
- Duplicate triangles: 0
- Coincident-disconnected vertices: 0
- Isolated vertices: 0
- Anchor vertices: 6, including 3 control anchors
- Free vertices: 1,146
- Modifier bind: TRUE
- Modifier evaluation: `evaluated_no_free_motion`
- Free-vertex maximum motion: 0.0

This distinguishes binding success from deformation evaluation failure. The component is a connected open surface with no nonmanifold, degenerate, duplicate, coincident-disconnected, or isolated-vertex defect.

## Step 2 — One cause at a time

**0/25 — FAIL.** The same component and the same native modifier operation were used for every variant.

| Intervention | Bind | Evaluation | Free motion |
|---|---|---|---:|
| Raw component | TRUE | no free motion | 0.0 |
| Remove isolated vertices | TRUE | no free motion | 0.0 |
| Remove degenerate and duplicate triangles | TRUE | no free motion | 0.0 |
| Separate unrelated components | TRUE | no free motion | 0.0 |
| Weld coincident vertices | TRUE | no free motion | 0.0 |
| Consistent triangle orientation | TRUE | no free motion | 0.0 |
| Add all open-boundary vertices as anchors | TRUE | no free motion | 0.0 |

The component has no isolated, degenerate, duplicate, or coincident-disconnected defects to repair. It is already a single connected component. Boundary anchoring and orientation correction did not change evaluation. Blender emitted `The system did not find a solution` during evaluation for the tested variants.

## Evidence and reproducibility

- Step 1 machine report: `step1-component-diagnostics.json`
- Step 2 machine report: `step2-component-repair-tests.json`
- Step 1 script: `scripts/diagnose_goal2_laplacian_components.py`
- Step 2 script: `scripts/test_goal2_laplacian_component_repairs.py`

Commands:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/diagnose_goal2_laplacian_components.py -- --source assets/tripo/vela-photoreal/generated-rigged.glb --goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --output verification/goal2-browInnerUp-proof/step1-component-diagnostics.json

& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/test_goal2_laplacian_component_repairs.py -- --source assets/tripo/vela-photoreal/generated-rigged.glb --goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --output verification/goal2-browInnerUp-proof/step2-component-repair-tests.json
```

No source GLB was modified. Step 3 solver-only topology construction, Step 4 real brow deformation, and Step 5 visual verification were not executed because Step 2 failed.
