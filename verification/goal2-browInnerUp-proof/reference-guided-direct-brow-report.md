# Goal 2 reference-guided direct brow test

## Reference video

The supplied worried/inner-brow-raise clip was downloaded from Drive and inspected at five time positions. It is approximately 5.04 seconds at 24 fps. The visible sequence includes a neutral start, gaze/head changes, strong eye widening, mouth opening, and a surprise-like peak. It is not an isolated browInnerUp performance. Because head motion and eyelid/eye activation are mixed with the brow motion, it was used qualitatively only. No independent numeric video landmark target was fitted. Avaturn remains the quantitative 3D target.

Reference file: `worried-reference.mp4`.

## Direct mesh method

The original high-resolution Tripo mesh is deformed directly. No coarse physics embedding, springs, muscles, donor transfer, or equilibrium solver is used.

- Brow anchors: Goal1 landmarks `70, 63, 105, 336, 293, 334`.
- Up direction: eye midpoint toward chin, reversed.
- Influence: compact normalized radial field with upper-forehead falloff and eyelid exclusion.
- Coincident vertices receive identical displacements.
- Amplitude is backtracked against triangle orientation and collapse at 25, 50, 75, and 100 percent.

## Results

| Model | Interocular width | Requested | Safe amplitude | Weighted achieved motion | New inversions | Collapsed triangles | Reimport |
|---|---:|---:|---:|---:|---:|---:|---|
| Female | 55.843 mm | 1.000 mm | 0.125 mm | 0.076 mm | 0 | 0 | PASS |
| Male | 299.743 mm | 1.000 mm | 0.250 mm | 0.152 mm | 0 | 0 | PASS |

All weights 0, 25, 50, 75, and 100 percent passed the geometric checks after export and reimport. The neutral mesh vertex and triangle counts are unchanged. Visual inspection shows no cracks or dark deformation artifacts, but the brow movement is too subtle to qualify as a convincing browInnerUp expression.

Evidence:

- Female measurements: `female-direct-brow-v2.json`
- Male measurements: `male-direct-brow-v2.json`
- Female integrity: `female-direct-brow-v2-integrity.json`
- Male integrity: `male-direct-brow-v2-integrity.json`
- Female renders: `female-direct-v2-render/`
- Male renders: `male-direct-v2-render/`

## Decision

The direct topology-preserving experiment is geometrically valid but expression-quality FAIL. The limiting mechanism is the local render topology: the required 1 mm field creates orientation failures before the eyebrows move visibly enough. No new custom physics solver was started.
