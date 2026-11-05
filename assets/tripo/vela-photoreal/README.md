# Vela photoreal Tripo character

## Preserved inputs

- `reference-image.png` is the clean single-image input prepared from the supplied character reference.
- `generated-original.glb` is the Tripo H3.1 output, preserved unchanged.
- `generated-rigged.glb` is Tripo's Mixamo auto-rig result, preserved unchanged.
- `vela-photoreal-faced.glb` is the Vela-ready derivative.

The original is a single closed surface with 999,787 vertices and about 1.94 million triangles, 4K base-color/normal/ORM textures, no skin weights, no armature, and no facial morphs. Tripo's rigged file adds 65 Mixamo bones and weights every vertex, but still has no facial shapes, jaw bone, eye bones, separate eyes, teeth, or tongue. Its untextured `Icosphere` helper is not used by the facial conversion.

## Character-specific facial conversion

`scripts/build_tripo_photoreal_face_rig.py` registers the 478-point MediaPipe landmarks against the Mixamo mesh using the same orthographic camera used to render the face. It creates actual relative vertex deformations for jaw opening, all 15 Oculus speech visemes, both blinks, bilateral smile/frown, and brow lift/down. These are procedural surface deformations on the closed Tripo shell, not a production facial rig.

The derivative adds a shape-keyed dark cavity proxy, plus the separate teeth and tongue meshes and their speech shape keys from Vela's bundled Avaturn avatar. The transfer preserves the donor UVs and embedded material textures. The Tripo face retains its identity surface, 4K PBR maps, and Mixamo skin. The original and rigged GLBs remain untouched. The derivative face is reduced with Blender's 0.30 Decimate ratio for browser rendering.

The dental fit scales to the Tripo mouth registration and applies the donor speech deltas. This provides real oral geometry and deformation controls, but the donor is not topologically matched to Tripo's face. Tripo's painted lips remain on the closed shell and visibly stretch when it opens. Current speech output has visible mouth artifacts and is not certified as convincing.

Rebuild without further Tripo API calls:

```powershell
blender -b --python scripts/build_tripo_photoreal_face_rig.py
```

The landmark detector is `scripts/detect_tripo_face_landmarks.py`; it requires MediaPipe and an external Face Landmarker task model. `landmarks.json` is the calibration input for this character.

## Runtime verification

`npm.cmd run test:tripo-photoreal` imports the derivative in terminal-driven Playwright Chromium, requests speech from the local HeadTTS service, checks the returned viseme timeline, samples mouth/blink/expression channels, and captures animation frames. The latest run returned HTTP 200 from `/v1/synthesize`, reported 15/15 speech visemes, 2/2 blink targets, 7 expression targets, an active audio context, and zero browser errors. It rendered in a 412 by 915 emulated phone viewport.

This verifies runtime wiring and morph activity during actual synthesized speech. It does not prove accurate visible phoneme shapes, face landmark accuracy, physical Android performance, or perceptual acceptance. See `verification/tripo-certification.md` for the sequential gate results.

## Known limitations

- The Tripo face is one closed surface with painted lips. The lips stretch as the shell opens and visible edges remain around the transferred mouth anatomy.
- The eyes are part of the same surface and texture. Blinks are generated skin deformations; independent eyeball gaze is unavailable because the source has no eye meshes or eye bones.
- Gate 4 fails. Gate 3 and Gates 5 to 9 are not certified.
- Phone viewport testing used desktop Chromium emulation, not a physical Android device.
- Rights for the Tripo avatar follow the account's applicable Tripo terms.

