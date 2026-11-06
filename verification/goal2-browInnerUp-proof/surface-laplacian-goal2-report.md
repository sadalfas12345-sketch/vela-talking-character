# Goal 2 deformation-transfer verification

## Coordinate system

Both GLBs import with identity object scale and scene unit scale 1.0. The
female target is approximately 168.34 x 324.70 x 981.19 mm in world bounds and
has a 55.843 mm Goal-1 interocular distance. The male target is approximately
842.65 x 889.79 x 980.67 mm and has a 299.743 mm interocular distance. The male
value is not a unit-transform error: its world matrix is identity and its
bounding height is similar to the female, but its width and facial proportions
are substantially larger. It must therefore be treated as a model-proportion
finding, not silently normalized away.

## Solver tested

The Gaussian field was replaced by a constrained surface-Laplacian solver. It
selects a local submesh from Goal-1 anatomical attachments, builds adjacency
from the imported target triangles, diffuses displacement over that graph, and
re-enforces donor brow and zero-motion eyelid, eye, nose, cheek, chin, and skull
constraints. A geometric validity projection attenuates only vertices in
inverted triangles.

The same source code was run on the female rigged GLB and the male unrigged GLB.

## Reimported results

| model | eye width | left brow | right brow | max eyelid | inversions | visual |
|---|---:|---:|---:|---:|---:|---|
| female | 55.843 mm | 0.296 mm | 0.542 mm | 0 mm | 0 | FAIL, too subtle and local brow artifact |
| male | 299.743 mm | 1.608 mm | 0.744 mm | 0 mm | 0 | FAIL, no convincing raise |

The surface solver preserves topology and eliminates measured winding flips, but
it does not preserve sufficient donor brow motion. It therefore does not meet
the visual acceptance criterion. No expression-strength scaling or
character-specific patch was added to force a pass.

## Evidence

- `coordinate-systems.json`
- `female-surface-laplacian-transfer.json`
- `male-surface-laplacian-transfer.json`
- `female-surface-laplacian-measurements.json`
- `male-surface-laplacian-measurements.json`
- `female-surface-laplacian-integrity.json`
- `male-surface-laplacian-integrity.json`
- `female-surface-laplacian-render/neutral.png`
- `female-surface-laplacian-render/browInnerUp_50.png`
- `female-surface-laplacian-render/browInnerUp_100.png`
- `male-surface-laplacian-render/neutral.png`
- `male-surface-laplacian-render/browInnerUp_50.png`
- `male-surface-laplacian-render/browInnerUp_100.png`

## Decision

**GOAL 2: FAILED.** The model-agnostic surface-aware solver is a reproducible
improvement over Gaussian interpolation for geometric validity, but it does not
yet transfer a convincing eyebrow raise to both models. Goal 3 was not started.
