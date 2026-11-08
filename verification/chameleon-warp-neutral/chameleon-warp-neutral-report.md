# Chameleon Warp neutral-face fitting

Date: 2026-11-08  
Branch: `wip/tripo-face-repair`  
Baseline commit: `1eabccc69fce073e49902ca0712cd218ab5e94a6`  
Chameleon Warp checkout: `C:\Users\USER\.codex\chameleon-warp`, commit `abbe529eb4d810d8de5a958338def99c1f502826`

## Method

I used the repository's native **Wrap** operation with the bundled USC ICT
FaceKit neutral mesh as the source template. The source is the redistributable
`demo_assets/ict-facekit/skin/generic_neutral_mesh.obj`, licensed under the
MIT license shipped in `demo_assets/ict-facekit/LICENSE-ICT-FaceKit.txt`.
The template has five accompanying neutral-topology expression meshes:
`jawOpen`, `mouthSmile_L`, `mouthSmile_R`, `eyeBlink_L`, and `eyeBlink_R`.

The target marker positions came from the existing Goal 1 3D surface records.
Thirty-six existing MediaPipe IDs were used, including eye, nose, mouth, jaw,
brow, and cheek points. Source marker vertices were selected by projecting the
same MediaPipe IDs onto an untouched ICT neutral render. No Tripo GLB was
modified and no Goal 1 or ARAP code was changed.

The Chameleon backend was run locally with its target-triangle cap raised only
to admit the existing Tripo targets, which are above the default Wrap cap.
The source and target were converted to OBJ for the documented API.

## Inputs and topology

| Model | Original vertices | Original polygons / triangles | Fitted template vertices | Fitted polygons / triangles |
|---|---:|---:|---:|---:|
| Female Tripo | 999,787 | 1,943,912 | 14,062 | 14,034 / 28,068 |
| Male Tripo | 991,219 | 1,897,687 | 14,062 | 14,034 / 28,068 |
| ICT source | 14,062 | 14,034 / 28,068 | — | — |

The fitted result inherits the ICT source topology, as expected from Chameleon
Warp Wrap. The neutral fitted OBJ had zero zero-area triangles in the simple
post-export check:

- Female: 0 / 28,068 degenerate triangles; minimum triangle area
  `2.14e-7` in fitted-template units.
- Male: 0 / 28,068 degenerate triangles; minimum triangle area
  `2.99e-6` in fitted-template units.

These checks do not imply a successful facial fit; they only describe the
output topology.

## Chameleon numerical results

| Model | Alignment scale | Mean residual | P95 residual | Max residual | Solver-damped fold events |
|---|---:|---:|---:|---:|---:|
| Female | 1224.7207 | 0.2387 | 1.2629 | 4.8161 | 9,339 at first iteration, decreasing to 4,891 |
| Male | 27.4225 | 0.1335 | 0.8419 | 5.0643 | 1,161 at first iteration, decreasing to 797 |

The residuals are in the fitted source-template coordinate system and are
reported by Chameleon Warp. They are not an independent anatomical accuracy
metric. The solver explicitly damped thousands of triangle flips during both
runs, which is a quality warning rather than a pass condition.

## Visual inspection

The actual fitted neutral meshes were rendered in clay and wireframe:

- [Female original clay](female/original-clay.png)
- [Female fitted clay](female/wrapped-clay.png)
- [Female original wireframe](female/original-wireframe.png)
- [Female fitted wireframe](female/wrapped-wireframe.png)
- [Male original clay](male/original-clay.png)
- [Male fitted clay](male/wrapped-clay.png)
- [Male original wireframe](male/original-wireframe.png)
- [Male fitted wireframe](male/wrapped-wireframe.png)

Codex vision inspection found severe spike-like and folded regions in the
fitted outputs, especially across the forehead, brow, and surrounding facial
surface. The result does not preserve the original facial identity closely
enough to replace either original face.

## Identity, continuity, textures, and blendshapes

- Facial identity: **FAIL** for both. The fitted surfaces contain obvious
  spikes and large local distortions.
- Neck, ear, eye, and mouth continuity: **FAIL / not acceptable** for both.
  The fitted output is a standalone ICT-topology mesh and the renders show
  severe local discontinuities rather than a production-ready replacement.
- Original Tripo textures: **not retained**. Chameleon Wrap exported an OBJ
  with source-template topology and UVs, but it did not transfer the original
  Tripo material images to that new topology.
- ICT blendshapes: **available as source neutral-topology meshes**, but their
  usability on these failed fitted results was not promoted to a pass. No
  expression fitting was performed, per scope.
- Original GLBs: preserved unchanged.

## Reproduction

The local Chameleon API run used the repository's documented endpoints:

```powershell
cd C:\Users\USER\.codex\chameleon-warp\backend
$env:DT_MAX_TARGET_TRIANGLES='2500000'
$env:DT_WORKSPACE_ROOT='C:\Users\USER\.codex\chameleon-warp\backend\workspace-neutral'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765

cd C:\Users\USER\.codex\chameleon-warp
py -3.11 scripts/build_chameleon_markers.py
py -3.11 scripts/run_wrap_api.py
```

The generated neutral outputs are retained outside the main repository at:

`C:\Users\USER\.codex\chameleon-warp\work\chameleon-female-wrapped.obj`  
`C:\Users\USER\.codex\chameleon-warp\work\chameleon-male-wrapped.obj`

## Decision

This is a completed neutral fitting attempt, but it is not an animation-ready
replacement. The failure is in the fitted surface quality and correspondence
stability, not in the source template's license or topology. I stopped here as
requested and did not attempt custom retopology, expression transfer, texture
transfer, or any Goal 1 / ARAP changes.

FEMALE: **FAIL**  
MALE: **FAIL**  
OVERALL STEP RESULT: **FAILED**
