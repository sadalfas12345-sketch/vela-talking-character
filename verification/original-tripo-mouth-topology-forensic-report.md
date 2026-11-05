# Original Tripo mouth topology forensic report

Status: **Gate 4 FAILED**

This report audits the exported V12 GLB and the one construction-level repair
candidate V15. The original Tripo GLBs were not modified. Avaturn supplied
motion measurements only.

## V12 exported-mesh findings

Evidence:

- GLB: `verification/vela-original-tripo-local-mouth-v12.glb`
- Audit: `verification/vela-original-tripo-local-mouth-v12-forensic.json`
- Close-up: `verification/vela-original-tripo-local-mouth-v12-forensic-render/`
- Source comparison: `verification/vela-original-tripo-local-mouth-boundary-comparison.json`

The original body has 999,787 vertices and 55,196 boundary edges. The V12
exported body has 999,437 vertices, 55,592 boundary edges, and zero edges used
by more than two faces. The body-level nonmanifold count therefore does not
explain the visible mouth defect.

The local exported objects are structurally defective:

| Object | Vertices | Edges | Faces | Boundary edges | Nonmanifold edges | Finding |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Lip boundary | 256 | 320 | 128 | 256 | 0 | 64 disconnected four-edge components, not upper/lower loops |
| Mouth cavity | 257 | 311 | 120 | 262 | 0 | disconnected ring/fan pieces, several non-cycle boundary components |
| Upper teeth | 41 | 55 | 20 | 50 | 0 | six disconnected fan components |
| Lower tongue | 35 | 51 | 20 | 42 | 0 | four disconnected fan components |

The lip object has a finite UV map and the original Tripo material. The cavity,
teeth, and tongue have no UV map. All four local objects are parented to
`mixamorig:Head`, so the transform hierarchy is consistent. The close-up shows
the cavity, teeth, tongue, and lip strip spatially separated. The black
fragments are original body triangles visible through the unstitched opening;
changing material lighting does not remove them.

## Root-cause classification

- A, landmark correspondence: not the V12 root cause. Existing correspondence
  evidence remains separate and does not validate the mouth topology.
- B, boundary selection: confirmed. V12 gathered all nearby boundary vertices
  and angle-sorted them instead of selecting one connected surgical boundary.
- C, topology/connectivity: confirmed. The exported lip boundary is not two
  continuous loops. The cavity, teeth, and tongue are separate open pieces.
- D, deformation constraints: not the primary cause. The independent control
  test fails before donor-motion quality can be judged.
- E, skinning/transform hierarchy: not the primary cause. All local objects use
  the head bone consistently.
- F, cavity/teeth/tongue construction: confirmed. The oral elements are
  disconnected and do not share a welded lip boundary.
- G, rendering/materials: secondary only. The artifact persists with local
  diagnostic materials and is caused by exposed geometry, not shader color.

## Reconstruction method selected

The public TopoRig implementation documents a seam-based approach using
coincident-vertex welding, MediaPipe lip seam splitting, ordered boundary
repair, cavity lining, and oral assembly fitting. Its published code and
checkpoints are restricted to noncommercial academic use, so it was evaluated
as an algorithmic reference only and was not copied into Vela production.

The controlled V15 repair implemented the applicable construction principle:

1. Keep only the connected projected front-surface face component closest to
   the measured mouth center.
2. Extract its boundary through mesh adjacency.
3. Require a closed cycle and order vertices by connected edges.
4. Build the local boundary from that ordered cycle rather than an unordered
   angle-sorted vertex set.

## V15 result

Evidence:

- Candidate: `verification/vela-original-tripo-local-mouth-v15.glb`
- Build report: `verification/vela-original-tripo-local-mouth-v15.json`
- Measurements: `verification/vela-original-tripo-local-mouth-v15-measurements.json`
- Full renders: `verification/vela-original-tripo-local-mouth-v15-render/`
- Forensic renders: `verification/vela-original-tripo-local-mouth-v15-forensic-render/`
- Independent controls: `verification/vela-original-tripo-local-mouth-v15-independent-lip-controls/`

The selection contained eight connected candidates. The chosen component had
173 faces and a mouth-center screen distance of 0.006656. Its pre-export
boundary was reported as one 331-vertex closed cycle. That is not sufficient:
the forensic close-up shows a long non-mouth tail in the supposed loop. After
GLB export/import, the lip object contains 1,324 vertices, 1,655 edges, 662
faces, and 1,324 boundary edges, demonstrating that the local construction is
still not a usable connected lip topology.

The independent commands moved the upper lip down and lower lip up by 3 mm,
without speech or donor weights. The rendered controls do not produce two
independent anatomical boundaries; they produce the same collapsed rim defect.

Measured mouth width is 0.0308348 m. The exported V15 aperture metric is:

| State | Aperture | Aperture / width | Normal flips |
| --- | ---: | ---: | ---: |
| Neutral | -0.0000188 m | -0.000609 | 0 |
| 50% jawOpen | not measurable because the paired loop is absent | not measurable | 0 |
| 100% jawOpen | not measurable because the paired loop is absent | not measurable | 2 |

The required targets of closed aperture at most 0.03W, open aperture at least
0.25W, and change at least 0.22W cannot be evaluated as passed because the
upper/lower loops do not exist in the exported topology. Gate 4 therefore
remains FAILED.

## Decision

The original Tripo mesh can support localized mouth reconstruction in
principle, but the current custom face-selection and separate-object tools do
not yet create a valid welded lip seam. The remaining work must use a genuine
surface-clipping or seam-insertion operation that creates new contour vertices,
welds them into the original body mesh, and constructs one connected oral
patch. Another cavity-depth, color, or offset iteration is not justified.

No donor face replacement was used. No full-face, forehead, temple, cheek, or
neck seam was introduced. Gates 5-9 remain UNVERIFIED.
