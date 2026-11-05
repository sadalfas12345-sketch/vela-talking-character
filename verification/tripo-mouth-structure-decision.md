# Tripo mouth topology decision

## Decision

**Gate 4: FAILED. Stop fitting the existing closed-shell mouth and the transplanted dental arches.** The current face does not reach the required full-open aperture, does not visibly close for `viseme_PP`, misses both blink-closure thresholds, and has measured intersections between the donor mouth meshes and the Tripo shell. Widening the opening or rescaling the same dental mesh would not fix the missing lip topology or stretched texture.

**Recommended structural route:** fit a complete animation-ready facial mesh from Vela's existing Avaturn reference to the Tripo face, then reproject/bake the Tripo appearance maps onto it. Keep the Tripo hair, clothing, body, and the source GLBs. This is the only compared route that provides compatible lip, eyelid, eye, and expression topology in one fit, so it has the best chance of passing all nine gates. It has a higher fitting and texture-baking cost, and likeness preservation must be measured at Gate 3.

A mouth-only patch is a lower-cost fallback for speech, but it cannot pass all nine gates by itself: the current separate blink measurement is already below Gate 4's 85% requirement. It would also need compatible eyelid surfaces or a separately proven eyelid deformation.

No facial geometry was changed during this diagnostic step. No Tripo credits were used.

## Source topology

The preserved original GLB has one scene mesh node and one primitive, with 999,787 vertices and 1,943,912 triangles. It has no morph targets. Its largest position-welded component contains 971,925 vertices; the global mesh has 4 boundary edges and 6 edges with more than two incident triangles. Those global edge counts include the whole character and do not identify mouth topology.

The Mixamo GLB still has one character mesh and 65 body bones, but no facial morph targets or separate lip, eye, teeth, or tongue nodes. The lip color is painted on the same face surface. The original does not have independently movable upper and lower lip meshes or a mouth aperture. The derived asset cuts 39 shell triangles at the mouth and adds a cavity proxy; this creates a visual gap but does not create upper/lower lip anatomy.

Evidence: `verification/tripo-mouth-topology.json`, `assets/tripo/vela-photoreal/inspection.json`, `assets/tripo/vela-photoreal/rigged-inspection.json`.

## Measured aperture and target mismatch

Live Chromium measured a neutral rendered mouth width of 57.460 mm, spanning 74.731 pixels. Registered mouth width in the builder is 30.834 mm; the observed runtime scale ratio is 1.8635.

At full `jawOpen`, the nearest rendered upper/lower lip surface vertices are 1.510 mm apart, or 0.0263W and 1.79 screen pixels. Gate 4 requires 0.25W, which is 14.365 mm or 18.683 pixels at this framing. The measured full-open lip separation is 10.5% of the required value. The `jawOpen` versus `viseme_PP` aperture difference is 0.895 mm or 0.0156W; the requirement is 0.22W or 12.641 mm.

The `viseme_PP` anchor gap is 0.0107W, under the numerical 0.03W closed-lip limit. But its rendered frame retains a large dark cavity and two visible dental rows. A dark-pixel envelope around the cavity spans 31 pixels, 0.415W. That envelope is a visual cavity proxy, not a true lip-contour measurement; the disagreement shows that the cavity proxy opens independently while the Tripo lip surfaces barely separate.

At full influence, O width is 0.919W, E width is 1.199W, and their difference is 0.280W. Left blink closure is 76.5%, right is 70.9%, below 85%. Left smile corner lift is 0.101W. The rendered full-influence frames are in `assets/tripo/vela-photoreal/verification/aperture-*.png`.

## Donor geometry fit and collisions

The Avaturn teeth mesh is 59.268 mm wide before fitting, versus the builder's 30.834 mm Tripo mouth. That is 1.922 times the target width and requires a 0.5203 horizontal scale. Its combined teeth envelope is 48.606 mm high. The builder's separate vertical scale of 0.2411 reduces this to 11.717 mm in builder space, 0.38W; after the measured runtime transform the envelope is about 21.835 mm.

The donor mesh has four disconnected dental components. The two higher and two lower components have a 12.300 mm overlap in the donor's vertical bounds. After fitting and runtime scaling, this is about 5.525 mm, or 0.096W. This is an envelope overlap measurement; the Blender BVH test separately confirms actual shell intersections.

At full `jawOpen`, Blender BVH finds 339 intersecting shell-teeth triangle pairs and 0 shell-tongue pairs. At full `viseme_PP`, it finds 341 shell-teeth pairs and 86 shell-tongue pairs. Counts are triangle pairs inside the mouth AABB, not unique intersection curves. The current frames also show the Tripo lipstick texture stretching over the open seam and dental geometry crossing its lip contour.

Evidence: `verification/tripo-gate4-measurements.json`, `verification/tripo-mouth-bvh-overlap.json`, `assets/tripo/vela-photoreal/verification/aperture-jawOpen.png`, `assets/tripo/vela-photoreal/verification/aperture-viseme_PP.png`.

## Structural options

| Approach | Gate coverage | Complexity and risk | Runtime cost |
|---|---|---|---|
| Replace only the mouth region with compatible lip topology | Can fix Gate 4 speech shapes and stop lip-texture stretching. It does not fix the measured blink failure by itself, so it cannot pass all nine gates without separate eyelid work. | Lower than a full face fit and preserves most of the Tripo face. Main risks are a visible patch seam, matching the Tripo skin texture, and registering lip landmarks. | Lowest added cost; only a small fitted patch plus cavity/teeth/tongue. |
| Fit a complete animation-ready facial mesh and transfer Tripo appearance | Supports mouth, eyelids, eyes, expressions, and speech through compatible topology; strongest basis for Gates 3-6 and coherent animation. | Highest preprocessing effort. Nonrigid fit and Tripo texture reprojection must preserve identity and avoid seams. | Likely modest. Vela's current Avaturn `Head_Mesh` has 3,663 vertices, 7,145 triangles, and 72 morphs; separate eye/eyelid meshes add hundreds of vertices. A fitted version can replace the existing face surface instead of layering another high-density face. Android performance still requires a physical-device test. |

**Recommendation:** the complete animation-ready facial mesh is the better route for the nine-gate objective. Vela's Avaturn head and eye assets are lightweight and already include facial morph targets. Fit that topology to the Tripo facial landmarks, project/bake Tripo's 4K appearance maps onto it, and keep the existing Tripo hair/body/outfit. If the fit cannot meet the Gate 3 landmark-error limits without changing identity, fall back to a mouth-plus-eyelid patch and report the remaining gate limitations explicitly.

## Certification state

Gate 4 is FAILED on the current derived asset. Gate 3 remains UNVERIFIED because independent manual landmark and neutral-drift measurements are not complete. Gates 5-9 are not certified; the required sequential run stops after the Gate 4 failure. The browser speech test did confirm TTS audio, timed visemes, and morph activity, but that does not override the geometric and visual Gate 4 failures.
