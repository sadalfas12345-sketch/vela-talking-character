# Tripo reference character

These are the preserved outputs from the single H3.1 multi-view generation using the supplied character reference sheet. Only the four isolated full-body views were submitted to the generation endpoint.

| Asset | Size | Inspection |
| --- | ---: | --- |
| `vela-reference-original.glb` | 23,856,804 bytes | 1 mesh, 261,084 vertices, 487,706 triangles, 3 textures. Base-color texture 8192 x 8192; normal and metalness textures 4096 x 4096. No bones or morph targets. |
| `vela-reference-rigged.glb` | 29,099,476 bytes | Tripo Mixamo body rig, 65 bones; all TalkingHead-required body bones map. No facial bones, no morph targets, no visemes, no blink targets, and no expression targets. |

Tripo's free rig-check reported a riggable biped. Its paid Mixamo rigging step added a body skeleton only. It did not create facial deformation. Vela's compatibility inspector reports both files as not activated, and leaves the default avatar selected. A jaw or eye bone cannot replace the absent face shapes needed for synchronized speech and blinking.

The rendered close-up was visually inspected. It preserves the supplied reference's face, hairstyle, and ivory outfit, with detailed textures. The neutral mouth is closed; Tripo topology inspection found no distinct upper/lower dental shells. No speaking animation is claimed for this character.

## Tripo usage

- One H3.1 multiview generation: 70 credits.
- One Mixamo body-rig conversion: 25 credits.
- Total consumed: 95 credits.
- Account balance checked after processing: 405 available, 0 frozen.
- No additional generation attempts were submitted.

## Exact conversion requirement

This GLB needs an actual facial-rig conversion that creates deformations on its facial surface: at minimum Oculus/ARKit-equivalent visemes including jaw opening and lip closure, plus independent eye-blink shapes and expression shapes. It also needs fitted inner-mouth geometry such as teeth/tongue if those are to be visible while speaking. Renaming morph targets cannot provide any of these missing deformations. After conversion, export a GLB with the new morph targets and re-run `npm run test:tripo` plus the actual Vela speech/motion checks.

The locally available Blender automatic face-rig candidates were assessed against the generated geometry. The CaptureForge FaceForge fit makes a bone rig from mapped landmarks, but does not itself bake a tested TalkingHead viseme set for this mesh. The Tripo Face Rig pipeline's mouth measurement returned no mouth profile because this model has no separate teeth geometry. The newly published OmniFaceRig page describes a four-model, 20-30 second pipeline benchmarked on an A100, but its released research materials are under a noncommercial research license and the repository does not provide a runnable inference pipeline. It is therefore not used as a production conversion here.

Run the repeatable browser compatibility check with:

```powershell
npm.cmd run test:tripo
```
