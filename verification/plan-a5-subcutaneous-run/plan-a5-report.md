# VELA Plan A5 — Subcutaneous-anchor facial spring experiment

Status: **STOPPED at Stage B**

Branch: `wip/tripo-face-repair`

Starting commit: `1e9840144273bef0793f0159604b7e0d3e776c80`

## Scope and stop rule

This run follows the Plan A5 Google Doc.  The A5 ablation requires an
anatomically clean facial-skin domain before either the no-anchor or supported
Hookean solve is run.  Stage B did not pass the required surface inspection, so
the dependent physics stages C–E were not started.  No original GLB was edited,
and no landmark trajectory was changed.

## Inputs

| Character | Original GLB | Existing/full mesh | Goal 1 attachment input |
|---|---|---|---|
| Female | `assets/tripo/vela-photoreal/generated-original.glb` | `verification/plan-a-hookean-run/female-full.npz` | `verification/plan-a5-subcutaneous-run/female-corrected-attachments.json` |
| Male | `assets/tripo/generalization-male-20261105/generated-original.glb` | `verification/plan-a-hookean-run/male-full.npz` | `verification/plan-a2-hookean-run/male-original-attachments.json` |

The female attachment audit found a source/target world-frame offset.  The
source-to-original alignment translation applied by the diagnostic raycast was
`[0.0000739358, -0.0004922152, 0.4902183712]` model units.  After this
correction, 478/478 female attachment records had finite front-surface hits.
This correction is an A5 diagnostic output; it does not modify Goal 1 or the
source GLB.

The male run reused the existing 478/478 attachment records without altering
them.

## Stage A — anchor mechanics and numerical unit tests

Commands:

```powershell
python scripts/test_plan_a4_solver.py
python scripts/test_plan_a5_subcutaneous_mechanics.py
```

Results:

- A4 baseline tests: **PASS**, including interior barycentric constraint,
  sparse redundant-row reduction, and zero-rest spring residual.
- A5 support-mechanics tests: **PASS**.
- Fixed inward-anchor finite-difference gradient maximum absolute error:
  `1.0256819699128172e-11`.
- Zero support-ratio energy contribution: `0.0`.
- Barycentric constraint rank test: rank `1`.

This establishes the small mechanics bookkeeping, not a facial solve.

## Stage B — anatomical surface inspection

The existing A3/A4 geodesic candidate was built at `0.50` interocular widths
for this inspection.  It preserves original vertex IDs and triangles but
retains disconnected surface pieces touched by the landmark region.

| Candidate | Vertices | Triangles | Topology components | Visual result |
|---|---:|---:|---:|---|
| Female `.50 IPD` patch | 41,747 | 79,627 | 16 | Face plus hair strands and neck surface |
| Male `.50 IPD` patch | 208,351 | 401,474 | 67 | Face plus beard/hair and neck/collar-adjacent surface |

The candidate-domain renders show the selected region in red over the original
textured render:

- `female-r050-domain.png`
- `male-r050-domain.png`

The rendered evidence is not an acceptable A5 skin segmentation.  The female
selection visibly includes front hair locks, loose side strands, and neck
surface.  The male selection visibly includes beard/hair structures and neck
surface.  A single GLB mesh/material prevents material-name filtering from
separating those structures.

An automatic normalized landmark-envelope candidate was also tested using the
same rule on both characters:

```powershell
python scripts/build_plan_a5_anatomical_domain.py `
  --mesh verification/plan-a-hookean-run/female-full.npz `
  --goal1 verification/plan-a5-subcutaneous-run/female-corrected-attachments.json `
  --output verification/plan-a5-subcutaneous-run/female-anatomical-candidate-r006.json

python scripts/build_plan_a5_anatomical_domain.py `
  --mesh verification/plan-a-hookean-run/male-full.npz `
  --goal1 verification/plan-a2-hookean-run/male-original-attachments.json `
  --output verification/plan-a5-subcutaneous-run/male-anatomical-candidate-r006.json
```

That candidate retained all attachment triangles, but did not solve the
classification problem:

| Candidate | Vertices | Triangles | Topology components | Attachment triangles forced outside envelope |
|---|---:|---:|---:|---:|
| Female normalized envelope | 101,575 | 194,051 | 56 | 0 |
| Male normalized envelope | 342,362 | 647,430 | 343 | 0 |

The corresponding visual checks are:

- `female-anatomical-candidate-r006.png`
- `male-anatomical-candidate-r006.png`

They still visibly include non-skin surfaces.  The female render contains
hair/side strands and neck; the male render contains beard/hair and neck/collar
regions.  The envelope also fragments the source surface into 56 and 343
components, respectively, so it is not a valid continuous facial-skin domain
for the required distributed seam graph.

### Stage B result

**FAIL.** The required anatomical domain is not established.  The failure is
not a numerical solver failure and no spring solve was run after this gate.
Adding virtual springs at this point would connect surfaces that the visual
inspection has shown are not all facial skin, which would violate the A5
requirements.

## Dependent stages

| Stage | Result | Reason |
|---|---|---|
| C — short contiguous sequence | NOT RUN | Stage B failed |
| D — frame 30 | NOT RUN | Stage B failed |
| E — all 121 frames | NOT RUN | Stage B failed |

No A5-control or A5-supported render, hard-constraint physics result, or full
animation result is claimed.

## Reproducibility

```powershell
cd C:\Users\USER\talking-character-demo
python scripts/audit_plan_a5_components.py `
  --female verification/plan-a5-subcutaneous-run/female-patch-r050.npz `
  --male verification/plan-a5-subcutaneous-run/male-patch-r050.npz `
  --output verification/plan-a5-subcutaneous-run/corrected-component-audit.json

python scripts/render_plan_a5_domain_audit.py `
  --glb assets/tripo/vela-photoreal/generated-original.glb `
  --graph verification/plan-a5-subcutaneous-run/female-patch-r050.npz `
  --camera verification/goal1-generalization-run/female-camera/discovered-camera.json `
  --output verification/plan-a5-subcutaneous-run/female-r050-domain.png
```

The equivalent male command substitutes the male GLB, patch, camera, and
output path.  The candidate-envelope commands are listed above.

## Recommendation before physics

Do not tune the A5 subcutaneous stiffness ratio yet.  First create and visually
verify a deterministic surface classifier that separates outer facial skin
from hair, beard, eyes/eyelashes, and neck on both original meshes while
retaining every required attachment triangle.  Only after that gate passes is
it valid to build the distributed virtual seam graph and run the A5
no-anchor-versus-supported ablation.

OVERALL STEP RESULT: **FAILED**

Failure gate: Stage B anatomical facial-surface domain was not established;
Stages C–E were correctly not run.
