# Tripo character repair: root-cause findings

## Geometry and rig

The preserved Tripo GLB is one character mesh object. It has 999,787 source vertices and 1,943,912 triangles. Position-welded topology analysis finds a dominant connected component of 971,925 vertices, plus four boundary edges and six edges with more than two incident triangles across the complete character. The face is not a separate facial mesh and has no independently movable upper/lower lips, eyes, teeth, tongue, or original facial morph targets. Lip color is painted on the face surface. Tripo's auto-rig adds 65 Mixamo body bones, not a facial rig.

The derivative removed 39 shell triangles around the mouth and added a cavity proxy. This exposes a dark shape but does not provide anatomically separate lips. The mouth animation moves the textured shell and stretches its painted lip region.

## Donor geometry and Gate 4 results

The Avaturn dental meshes are 1.922 times wider than the builder's Tripo mouth before fitting. The transferred teeth need 0.5203 horizontal scale and 0.2411 vertical scale. The donor's upper and lower dental components overlap by 12.3 mm in their source vertical bounds, which becomes an estimated 5.525 mm or 0.096 of the runtime mouth width after fitting.

At runtime the neutral mouth width is 57.460 mm. Full `jawOpen` produces 1.510 mm of separation between the registered upper/lower shell lip vertices, 0.0263W. Gate 4 requires 0.25W or 14.365 mm. The open/closed difference is 0.0156W against a 0.22W requirement. Left/right blink closure is 76.5% and 70.9%, below 85%.

Blender BVH overlap testing finds 339 shell/teeth triangle pairs at full jaw open. At full `viseme_PP`, it finds 341 shell/teeth pairs and 86 shell/tongue pairs. The `viseme_PP` image still shows an open dark cavity and separated dental rows. Full-influence screenshots visibly show stretched Tripo lipstick texture and dental meshes crossing the lip contour.

**Gate 4 is FAILED. Stop tuning the current shell and transferred dental geometry.** The browser speech test confirms that TTS and timed visemes reach the channels, but this does not overcome the visible and measured articulation failures.

See `verification/tripo-mouth-structure-decision.md` for measurements, thresholds, evidence, and the comparison of structural replacements.

## Structural decision

A mouth-only topology patch could fix speech aperture with relatively low runtime cost, but it does not fix the measured blink failure by itself. The recommended route for the full nine-gate objective is to nonrigidly fit a complete animation-ready facial mesh, including eyelids, eyes, lips, and oral meshes, to Tripo's landmarks, then bake/reproject Tripo's appearance maps onto it. Retain Tripo hair, body, clothing, and original GLBs. Vela's Avaturn `Head_Mesh` contains 3,663 vertices, 7,145 triangles, and 72 morphs, with separate lightweight eye and eyelid meshes; this is a feasible runtime base. Gate 3 must validate landmark error and identity preservation before calling the fit acceptable.

No Tripo API credits were used. Original and Mixamo GLBs remain unchanged. The current derivative is experimental and does not pass Gate 4.
