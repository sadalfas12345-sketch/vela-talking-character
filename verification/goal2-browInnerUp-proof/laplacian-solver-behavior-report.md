# Native Blender Laplacian Solver Behavior Audit

Branch: `wip/tripo-face-repair`  
Diagnostic commit baseline: `9bdb3d0a27becd9acf16e6d63dd8831f78efee0e`

This run is diagnostic only. It does not alter or export either Tripo GLB, and it does not change Goal 1, landmark extraction, or expression transfer.

## Test harness

Script: `scripts/diagnose_goal2_laplacian_solver_behavior.py`

The harness imports the female original Tripo GLB, reconstructs the same local proxy, extracts one connected component, creates a temporary mesh, binds Blender 5.2.3's native `LAPLACIANDEFORM` modifier, moves one bound anchor after binding, evaluates the dependency graph, and measures the evaluated anchor and non-anchor vertices. All experiments use the same component topology unless explicitly identified as the second-component generalization check.

Command for component 30:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/diagnose_goal2_laplacian_solver_behavior.py -- --source assets/tripo/vela-photoreal/generated-rigged.glb --goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --component 30 --output verification/goal2-browInnerUp-proof/solver-behavior-component30.json
```

Command for the second component check:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/diagnose_goal2_laplacian_solver_behavior.py -- --source assets/tripo/vela-photoreal/generated-rigged.glb --goal1 verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --component 1 --output verification/goal2-browInnerUp-proof/solver-behavior-component1.json
```

Raw machine results:

- `solver-behavior-component30.json`
- `solver-behavior-component1.json`

## Step 1 — baseline, component 30

**Result: PASS, 20/20.**

Measured component:

| Metric | Actual |
|---|---:|
| Vertices | 1,152 |
| Triangles | 2,122 |
| Connected components | 1 |
| Bounding-box diagonal | 0.04739897571 |
| Average edge length | 0.000744161267 |
| Minimum edge length | 0.000114061719 |
| Open boundary edges | 180 |
| Nonmanifold edges with more than two incident triangles | 0 |
| Zero-area triangles | 0 |
| Duplicate triangles | 0 |
| Coincident disconnected groups | 0 |
| Isolated vertices | 0 |
| Anchors | 6 |
| Free vertices | 1,146 |
| Requested anchor motion | 0.000473989757 |
| Native bind | true |
| Evaluated anchor motion | 0.000473991036 |
| Maximum free-vertex motion | 0 |
| RMS free-vertex motion | 0 |

Blender emitted the native warning `The system did not find a solution` during evaluation. Binding succeeded; the failure is evaluation behavior, not bind failure. The moved anchor itself follows the requested displacement, but the free surface remains unchanged.

## Step 2 — coordinate scale

The same component, faces, and six anchors were tested at each scale. The requested displacement was always 1% of that scaled component diagonal. Values below are normalized by the scaled diagonal.

| Scale | Bind | Anchor motion / diagonal | Free max / diagonal | Free RMS / diagonal | Result |
|---:|---|---:|---:|---:|---|
| 0.01 | true | 0.0100000663 | 9.4536e-7 | 5.6705e-7 | effectively no surface motion |
| 0.1 | true | 0.0100000663 | 6.3029e-7 | 4.3371e-7 | effectively no surface motion |
| 1 | true | 0.0100000270 | 0 | 0 | no surface motion |
| 10 | true | 0.0046409587 | 0.0258246267 | 0.0138941470 | nonzero but badly conditioned/attenuated |
| 100 | true | 0.0046406537 | 0.0261142472 | 0.0140263414 | nonzero but badly conditioned/attenuated |

**Conclusion:** coordinate scale changes the numerical behavior. At scales 0.01–1, free motion is zero or below 1e-6 normalized diagonal. At scales 10–100, free motion appears, but the moved anchor reaches only about 46.4% of the requested normalized motion. Scale sensitivity is confirmed, but scaling alone does not repair the original-scale failure.

## Step 3 — anchor configuration

The same original-scale component and 1%-diagonal request were used. No mesh connectivity was changed.

| Configuration | Anchors | Bind | Evaluated anchor / diagonal | Free max / diagonal | Result |
|---|---:|---|---:|---:|---|
| A: three widely separated | 3 | true | 0.0100000270 | 0.0100000270 | genuine free-surface motion |
| B: six original | 6 | true | 0.0100000270 | 0 | no free-surface motion |
| C: three control plus three stationary | 6 | true | 0.0100000270 | 0 | no free-surface motion |
| D: existing original | 6 | true | 0.0100000270 | 0 | no free-surface motion |

The three-anchor configuration is geometry-derived from the component and is not a hard-coded vertex selection. The six-anchor arrangements are the configurations that reproduce the prior failure. Blender emitted `The system did not find a solution` for the no-motion evaluation cases.

**Conclusion:** the failure depends on anchor configuration, specifically the additional stationary constraints in this component. Open boundary edges are not sufficient by themselves to explain the failure: the same open component deforms with three anchors, without changing topology.

## Step 4 — modifier-evaluation isolation

The four requested combinations were evaluated on component 30:

| Configuration | Bind | Free max / diagonal | Conclusion |
|---|---|---:|---|
| Original geometry + original anchors | true | 0 | reproduces failure |
| Best numerical scale + original anchors | true | 6.3029e-7 | effectively no deformation |
| Original geometry + three-anchor arrangement | true | 0.0100000270 | genuine free deformation |
| Best numerical scale + three-anchor arrangement | true | 0.0100000270 | genuine free deformation |

The moved free vertices are not merely the moved anchor itself: in the working three-anchor configuration, a non-anchor vertex reaches the same normalized maximum displacement and the free-vertex RMS is `0.0002950130` of the component diagonal at original scale.

## Step 5 — second component generalization

Component 1 was selected independently from the same Tripo-derived proxy and tested with the same script and rules.

| Metric | Component 1 actual |
|---|---:|
| Vertices | 5,385 |
| Triangles | 10,413 |
| Bounding-box diagonal | 0.09490227046 |
| Open boundary edges | 355 |
| Nonmanifold edges | 0 |
| Baseline six-anchor free max / diagonal | 0 |
| Three-anchor free max / diagonal | 0.0099999866 |
| Three-anchor free RMS / diagonal | 0.0001363100 |

The same anchor-configuration dependency reproduces on a second Tripo-derived component. This supports a native modifier conditioning/constraint interaction rather than a defect unique to component 30.

## Decision

Most supported cause, in order:

1. **Anchor configuration / numerical constraint interaction — confirmed.** Six anchors, including the original stationary constraints, bind but produce no free-surface solution on both tested components. Removing the additional constraints and retaining three geometry-separated anchors produces nonzero free-surface deformation without topology changes.
2. **Coordinate-scale sensitivity — confirmed as a contributing numerical factor.** Scaling changes the normalized response, but does not explain the original-scale baseline by itself.
3. **Topology failure — not supported by this experiment.** The tested component has open boundaries but zero nonmanifold, degenerate, duplicate, coincident-disconnected, and isolated-vertex defects. The unchanged component deforms with the three-anchor arrangement.
4. **Modifier-evaluation workflow — not the primary cause.** The modifier is bound before anchor movement, the moved anchor evaluates at the requested location, and the three-anchor configuration produces non-anchor motion using the same workflow.

## Scope conclusion

The native Blender Laplacian modifier is **not universally reliable with the current six-anchor configuration at the original Tripo scale**. It is viable for a controlled component test when the anchor set is reduced to three geometry-separated anchors, but this is not yet proof that the full 468-landmark facial bake is valid. No full-character bake was attempted because the requested task was solver diagnosis only.

Recommended next experiment: test a model-agnostic anchor-selection rule that retains the minimum geometrically independent anchor basis for each connected solver component, then validate it on a second component and both characters before any full expression bake. If the application requires the full six-anchor or 468-control configuration, native Laplacian should be treated as failed for that configuration and compared against libigl ARAP in a separate authorized experiment.

## Scorecard

| Step | Score | Result |
|---|---:|---|
| Step 1: baseline reproduction | 20/20 | PASS |
| Step 2: coordinate scale | 25/25 | PASS — diagnostic completed; no universal repair |
| Step 3: anchor configuration | 25/25 | PASS — dependency isolated |
| Step 4: evaluation isolation | 20/20 | PASS — working controlled configuration identified |
| Step 5: decision and generalization | 10/10 | PASS — repeated on component 1 |
| **Diagnostic score** | **100/100** | **PASS** |

`BLENDER LAPLACIAN RESULT: FAILED for the original six-anchor Tripo configuration; CONDITIONALLY VIABLE for the tested three-anchor controlled configuration.`

`OVERALL STEP RESULT: FAILED`
