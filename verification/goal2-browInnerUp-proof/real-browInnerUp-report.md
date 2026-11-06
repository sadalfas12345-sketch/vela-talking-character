# Goal 2 final real Avaturn browInnerUp transfer

## Method

Avaturn's actual `Head_Mesh__Key__browInnerUp` was sampled at the six Goal 1
brow attachments using their stored donor triangle and barycentric coordinates.
The displacement vectors were transformed from the donor anatomical frame into
each target anatomical frame and scaled by target/donor interocular distance.
The existing orientation-constrained sparse QP then solved the original Tripo
vertices. No target vertex IDs, offsets, or character-specific masks were added.

Interocular scale factors were 0.611549 for the female and 3.282559 for the
male. The resulting target motions are therefore proportional to facial scale,
not arbitrary GLB dimensions.

## Reimported quantitative results

| Model | Requested motion, max | Achieved motion, max | Per-anchor ratios | Max eyelid movement | Inversions | Visual |
|---|---:|---:|---|---:|---:|---|
| Female | 5.134 mm | 5.312 mm | 82.9%, 98.9%, 96.4%, 103.5%, 101.4%, 97.4% | 0.0063 mm | 0 at all weights | FAIL |
| Male | 27.558 mm | 27.156 mm | 89.4%, 103.6%, 98.2%, 98.5%, 100.0%, 100.0% | 0.0016 mm | 0 at all weights | PASS geometry, visual review pending concern |

The five-weight integrity sweep covered 0%, 25%, 50%, 75%, and 100%. Both
models had zero zero-area, collapsed, or newly inverted triangles at every
weight after GLB export and reimport. Eyes, eyelids, and nose remained nearly
stationary numerically.

## Visual finding

Codex vision inspection of the actual reimported full-weight renders found a
conspicuous dark triangular brow-region artifact on the female, with a visibly
unnatural brow transition. This is a visual failure even though the mesh
integrity and displacement constraints pass. The male has visible brow motion
and stable surrounding anatomy, but the overall Goal 2 gate cannot pass while
the female artifact remains.

The female's first brow anchor also achieves only 82.9% of its very small
0.0117 mm requested motion. The remaining five anchors meet or exceed 90%.

## Evidence

- Motion derivation: `female-real-brow-motion.json`, `male-real-brow-motion.json`
- Female measurement: `female-real-qp-measurements.json`
- Male measurement: `male-real-qp-measurements.json`
- Female integrity: `female-real-qp-integrity.json`
- Male integrity: `male-real-qp-integrity.json`
- Female renders: `female-real-qp-render/`
- Male renders: `male-real-qp-render/`

## Decision

Goal 2 remains FAILED. The solver and export integrity pass, but the real
donor-motion visual gate fails on the female. No Goal 3 work was started.
