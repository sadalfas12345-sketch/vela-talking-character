# Plan A2 Hookean facial animation — result

Branch: `wip/tripo-face-repair`  
Baseline audit: `3f7cb9768dbf189f85091bb26f00d13179bf724e`

## Result

**OVERALL STEP RESULT: FAILED**

The experiment produced actual deformed original-mesh trajectories and independent validation, but the prescribed Hookean stretching-only model did not reach stable, visually valid facial equilibria. Hard landmark constraints were met numerically while the surrounding mesh became physically invalid.

## Inputs and provenance

| Item | Female | Male |
|---|---:|---:|
| Original GLB | `assets/tripo/vela-photoreal/generated-original.glb` | `assets/tripo/generalization-male-20261105/generated-original.glb` |
| Original vertices | 999,787 | 991,219 |
| Original triangles | 1,943,912 | 1,897,687 |
| Plan A2 reconstructed IPD | 0.0575601676 | 0.3040985113 |
| Exact original-GLB raycast attachments | 478/478 | 478/478 |

The raw validated archive contains 468 trajectories, IDs 0–467. The existing stabilized expression table contains 478 rows per frame; IDs 468–477 are table-derived iris trajectories and are not relabeled as raw validated data. There are 121 frames, so the run defines 57,838 frame-landmark targets per character. All 57,838 targets use the existing stabilized 2D table. The unmeasured depth channel is explicit `dz=0` in each target character's local facial-depth axis, while every landmark retains its own neutral 3D position.

The female Goal 1 report was found to reference `generated-rigged.glb`, not the requested original GLB. Its stored world-space positions and topology were therefore not reused as female original coordinates. Plan A2 created an unmodified, reproducible original-GLB attachment cache by reusing the existing landmark image locations and raycasting the exact original asset. The original Goal 1 report remains untouched. The cache has 478 geometric hits, but the female attachment cache still needs independent anatomical visual review; a successful raycast alone is not proof that every hit is facial skin.

## Facial spring graph

The computational domain uses a 0.01 interocular-width geodesic radius from the 478 attachment vertices. It retains original vertex IDs and original render triangles; no source GLB topology was welded, deleted, or retopologized.

Virtual seam candidates use the same rules on both characters: compatible non-eye components only, nearest eight boundary candidates per boundary vertex, gap no greater than 0.03 IPD, and boundary-normal dot product at least 0.65. One shortest compatible spring is retained per component pair. These are recorded separately from original mesh-edge springs.

| Graph metric | Female | Male |
|---|---:|---:|
| Solver vertices | 4,149 | 8,670 |
| Solver triangles | 5,072 | 10,787 |
| Original topology components in domain | 180 | 394 |
| Original edge springs | 9,070 | 19,066 |
| Virtual seam springs | 140 | 80 |
| Spring components after virtual links | 69 | 320 |
| Boundary vertices | 2,876 | 5,752 |

The virtual springs reduce fragmentation but do not make the entire facial domain physically connected. That remaining fragmentation is measured, not hidden. The first female failed component has 753 vertices, 999 triangles, and 110 landmark constraints. At frame 2, substep 10, its largest target movement is 0.0002229 model units, only 0.178 times its median local edge length, yet the constrained Hookean update produced a 238.1-unit maximum step and failed to reach equilibrium. This is an ill-conditioned local constraint/spring block, not a lack of target motion.

## Solver

The physical terms are only uniform Hookean axial stretch/compression on original mesh edges and the recorded virtual seam edges. No bending, volume, ARAP, support stiffness, gravity, inertia, damping, or spring-force cap was used. Landmark positions are exact barycentric equality constraints.

The position update is sparse Gauss–Newton with an equality-constrained KKT solve. A zero-mean translation/rotation gauge was added after the first diagnostic trajectory exposed unconstrained rigid modes. The gauge is a mathematical null-space selection: it pins no vertex and adds no physical support energy.

## Actual trajectory results

The initial diagnostic trajectory evaluated all 121 frames on both original meshes using one transition solve per frame. It is retained as evidence, not as a valid final animation.

| Measurement | Female | Male |
|---|---:|---:|
| Frames evaluated | 121/121 | 121/121 |
| Runtime | 105.62 s | 260.16 s |
| Defined hard targets | 57,838 | 57,838 |
| Targets within 1e-8 model units | 57,838 | 57,838 |
| Maximum error / IPD | 6.36e-11 | 7.94e-12 |
| Maximum edge extension strain | 7.20e32 | 5.56e31 |
| Maximum edge compression strain | -1.0 | -1.0 |
| P95 strain at worst frame | 61,605 | 169.50 |
| Maximum inverted triangles in a frame | 1,858 | 4,801 |
| Total inverted-triangle frame counts | 199,751 | 441,114 |
| Newly collapsed triangles by 0.1% area threshold | 0 detected, minimum area ratio 0.0135 | 0 detected, minimum area ratio 0.2678 |
| Maximum coincident-pair disagreement | 719.96 | 110.41 |
| Robust self-intersection test | Not available | Not available |

The enormous strain and duplicate disagreement are numerical evidence of mesh destruction, not meaningful facial motion. The lack of detected collapse under the selected area threshold does not rescue the result because orientation inversions and edge blow-up are already present.

## Required incremental path

The required 20-substep path was tested with the same model and hard targets.

- Female: failed at frame 2, substep 10, component 7. Constraint residual was `1.08e-9`, but projected spring residual was `124.84`, maximum update was `238.10`, and the block reached its four-iteration limit.
- Male: first three frames and their 20-substep transitions completed without a hard-constraint failure, but the maximum projected residual was `169.87` at the four-iteration limit. This is not an equilibrium pass.

The female failure record is in `female-failure-component-7.json`. It identifies the affected component, landmark IDs, target magnitudes, edge-length ratios, and exact failure frame.

## Visual inspection

The original GLBs were baked only in memory for diagnostic rendering. They were not overwritten. Neutral and failure-frame renders are in:

- `female-renders/frame-000.png`, `frame-096.png`, `frame-113.png`
- `male-renders/frame-000.png`, `frame-095.png`, `frame-113.png`

The neutral male render is recognizable. The female diagnostic camera needs the same anatomical review as its reattached landmark cache. The deformed female and male renders show severe spike-like excursions and detached-looking surface fragments, consistent with the measured strain and inversions. They are visual FAIL results, not acceptable facial animation.

## Commands

The main scripts are:

- `scripts/raycast_plan_a2_original_attachments.py`
- `scripts/build_plan_a_geodesic_patch.py`
- `scripts/build_plan_a2_spring_graph.py`
- `scripts/build_plan_a2_targets.py`
- `scripts/solve_plan_a2_hookean.py`
- `scripts/validate_plan_a2_hookean.py`
- `scripts/audit_plan_a2_failure_component.py`
- `scripts/render_plan_a2_hookean_frames.py`

The exact commands and output paths are preserved in the repository report and can be rerun from the repository root.

## Plan A2 status

- Constraint pass: **FAIL** as a complete Plan A2 claim, because the numerical targets are met in the diagnostic path but the required stable equilibrium path is not completed and the female original attachments need anatomical confirmation.
- Physics pass: **FAIL**. The Hookean solver does not reach stable equilibrium on the required incremental path.
- Visual pass: **FAIL**. Actual renders contain severe spikes, inversions, and detached-looking fragments.
- Original assets: preserved and unchanged.
- Production GLB export: not created because validation failed.

