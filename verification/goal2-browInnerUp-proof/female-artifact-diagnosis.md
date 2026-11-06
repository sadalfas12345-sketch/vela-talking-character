# Female real browInnerUp artifact diagnosis

## Frame test

The original frame used one eye corner and chin. A second model-agnostic frame
was tested using both eye centers, nose tip, and chin. It changes the rotation
matrices but preserves the six donor displacement magnitudes exactly:

`0.0117, 0.2711, 1.4999, 5.1341, 0.1101, 0.9681 mm` for the female.

The same dark triangular artifact remains in the female full-weight render.
Therefore the anatomical frame is not the confirmed cause.

## Donor correspondence

The six Avaturn barycentric attachments reproduce the same displacement vectors
for both target runs. The asymmetry is present in the actual Avaturn
`Head_Mesh__Key__browInnerUp` morph data, not introduced by target scale or
character-specific code. The largest vector is landmark 336 at 5.134 mm after
female interocular scaling. Landmark 70 is only 0.0117 mm, so it is not a
meaningful brow-motion anchor for the 90% criterion.

## Affected geometry

The female exported/reimported real-motion mesh was inspected directly. The
largest-motion triangles are clustered around target landmark 336:

- triangles 1057077, 1057078, 1057079, 1057076, 1052302, and 1052301
- affected vertices include 454815, 455106, 455134, 454924, 454819, 455142,
  and 455909
- maximum vertex displacement: 5.3124 mm
- maximum normal change over the mesh: 16.7375 degrees
- affected triangles use material index 0
- integrity reports zero winding flips, zero zero-area triangles, and zero
  collapsed triangles at 0%, 25%, 50%, 75%, and 100%

The artifact is therefore a local surface/material shading discontinuity caused
by the large donor-derived motion at the 336 attachment, not a topology
inversion or camera error. A per-character reduction would violate the
model-agnostic and actual-donor-motion requirements.

## Decision

The artifact is not safely fixed by the tested frame correction. The current
real-motion transfer remains visually FAILED on the female and must not be
marked complete. The safe next repair is to independently revalidate the 336
anatomical attachment and the donor morph's corresponding brow region before
changing the QP target; no Goal 1 or Goal 3 work was started.
