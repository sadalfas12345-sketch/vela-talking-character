# Plan A1 Hookean Input Audit

Status: **FAILED PRECONDITION**

The experiment stopped before spring equilibrium. The original assets and
stored motion data do not currently provide the two prerequisites required by
the requested Plan A formulation: a validated 3D target trajectory and one
connected facial-skin spring network.

## Motion coverage

- Raw validated archive: 121 valid frames, IDs 0-467 only.
- Existing normalized expression table: 121 rows, IDs 0-477, stabilized 2D coordinates.
- IDs 468-477 are present in the normalized table, but not in the raw validated
  archive. Their raw tracking provenance is therefore not independently
  verified by the existing archive.
- Fully measured head-stabilized 3D trajectories: **0**.
- Neutral 3D attachments from Goal 1: 478/478 on both characters.
- The audit did not invent depth. Using `dz=0` would be an explicit unmeasured
  embedding, not observed donor motion, so it was not used for a Plan A pass.

## Original-topology geodesic audit

The same multi-source Dijkstra selection rule was used on both original GLBs:
seed at all Goal 1 attachment vertices and retain original faces incident to a
vertex within 0.5 interocular widths along the original edge graph.

| Model | Eye width | Solver vertices | Solver triangles | Components | Boundary vertices |
|---|---:|---:|---:|---:|---:|
| Female | 0.0558428857 | 672,835 | 1,276,197 | 251 | 69,230 |
| Male | 0.2997431104 | 221,695 | 426,574 | 78 | 16,663 |

These are temporary views of the original topology, not modified meshes. No
vertices were welded, retopologized, deleted, or written back to the GLBs.

The largest connected component is recorded in
`plan-a-input-audit.json`. The full component lists remain in the generated
patch reports. The component counts and very large boundary sets demonstrate
that this is not a single connected facial skin network. A spring solve over
these disconnected pieces would not satisfy the stated “connected network”
principle; it would be a collection of independently bounded fragments.

## Why the solver was not run

Running Hooke equilibrium with fabricated depth and treating the disconnected
fragments as one face would produce measurements that do not represent the
requested experiment. Therefore no spring stiffness, boundary force, bending
term, ARAP term, or target attenuation was introduced. No deformed renders or
per-frame accuracy values are claimed.

## Reproduction

```powershell
blender -b --python scripts/extract_plan_a_full_mesh.py -- `
  --source assets/tripo/vela-photoreal/generated-original.glb `
  --output verification/plan-a-hookean-run/female-full.json

blender -b --python scripts/extract_plan_a_full_mesh.py -- `
  --source assets/tripo/generalization-male-20261105/generated-original.glb `
  --output verification/plan-a-hookean-run/male-full.json

python scripts/build_plan_a_geodesic_patch.py --mesh verification/plan-a-hookean-run/female-full.npz `
  --goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json `
  --output verification/plan-a-hookean-run/female-geodesic.json --radius-eye-width 0.5

python scripts/build_plan_a_geodesic_patch.py --mesh verification/plan-a-hookean-run/male-full.npz `
  --goal1 verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json `
  --output verification/plan-a-hookean-run/male-geodesic.json --radius-eye-width 0.5

python scripts/audit_plan_a_hookean_inputs.py `
  --video-landmarks verification/goal2-browInnerUp-proof/step1/video_landmarks.json `
  --expression-table verification/goal2-browInnerUp-proof/worried-expression-table.json `
  --female-goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json `
  --male-goal1 verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json `
  --female-patch verification/plan-a-hookean-run/female-geodesic.json `
  --male-patch verification/plan-a-hookean-run/male-geodesic.json `
  --output verification/plan-a-hookean-run/plan-a-input-audit.json
```

Recommended next intervention: obtain or validate per-frame depth for the
tracked 478 landmarks and use a clean connected facial simulation surface or a
documented topology-preserving connection layer. That is outside this
stretching-only run and requires authorization before changing the inputs.
