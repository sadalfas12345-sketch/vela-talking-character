# Female Tripo retopology v3 inspection

## Job

- Provider: Tripo official v3 mesh decimate / retopology
- Task ID: `78907f52-1f15-42ff-81a8-faf3a8aaacf5`
- Input: `assets/tripo/vela-photoreal/generated-original.glb`
- Output: `female-retopology-v3.fbx`
- Settings: `model=v3.0`, `quad=true`, `smart_uv=true`, `bake=true`, `face_limit=10000`
- API credits spent: **40**
- Original input preserved: **yes**
- Male model processed: **no**

## Geometry inspection

| Measurement | Original | Retopologized output |
|---|---:|---:|
| Mesh objects | 1 | 1 |
| Vertices | 999,787 | 9,650 |
| Polygons | 1,943,912 | 10,222 |
| Materials | 1 | 1 |
| UV layers | 1 | 1 |
| Degenerate polygons detected | 0 | 0 |

The output is a single simplified mesh with UV data and one material. The returned asset contains 10,222 polygons, which is above the requested 10,000 face limit as measured by the local Blender inspection. This may reflect the service's interpretation of the limit or FBX conversion, but it is not reported as meeting the limit exactly.

## Visual inspection

The clay front and profile views show that the broad female body silhouette, hair mass, hands, and clothing are retained. The available inspection renders are:

- [Original six-view front clay](six-original/xpos.png)
- [Retopologized six-view front clay](six-retopo/xpos.png)
- [Original six-view profile clay](six-original/yneg.png)
- [Retopologized six-view profile clay](six-retopo/yneg.png)
- [Retopologized full front wireframe attempt](retopologized-front-wireframe.png)
- [Retopologized full profile wireframe attempt](retopologized-profile-wireframe.png)

The wireframe renders are not reliable facial close-ups: the automatic camera framing places the face at the upper image boundary and the close-up topology around the eyes, brows, and mouth is not sufficiently resolved in the saved evidence. No facial identity or fitting-error claim is made from those images.

## Required checks

- Facial identity: broad silhouette appears retained, but a close facial comparison is **unverified**.
- Facial textures: UV/material data exists, but texture identity and baked texture fidelity are **unverified** from the saved clay renders.
- Eye, eyebrow, and mouth loops: **unverified**. The available output evidence does not establish clean anatomical loops.
- Continuity, holes, and degenerate polygons: one mesh object and zero degenerate polygons were measured; holes and cross-region continuity were not certified by the available inspection.
- Hair, body, and hands: broad geometry is visibly retained in front/profile clay views.
- Animation suitability: **not established**. Quad count and a single material do not prove animation-ready facial edge flow, and the facial loops were not independently verified.

## Decision

**FEMALE: FAIL**

The paid retopology request completed, but the inspection evidence is insufficient to certify facial animation suitability. The output should remain a separate experimental asset and must not replace the original GLB. No further paid operation was made, and the male was not processed.

## Reproduction

The API submission is reproducible with the committed script, using `TRIPO_API_KEY` from the configured environment without printing it:

```powershell
python scripts/run_tripo_female_retopology.py
```

The output inspection scripts are:

```powershell
python scripts/inspect_tripo_female_retopology.py -- \
  assets/tripo/vela-photoreal/generated-original.glb \
  verification/tripo-female-retopology-v3/female-retopology-v3.fbx \
  verification/tripo-female-retopology-v3 \
  verification/goal1-generalization-run/cross-character-accuracy/female/refined-camera.json

python scripts/render_six_mesh_views.py -- \
  verification/tripo-female-retopology-v3/female-retopology-v3.fbx \
  verification/tripo-female-retopology-v3/six-retopo
```

