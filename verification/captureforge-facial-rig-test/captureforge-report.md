# CaptureForge facial rig test

Date: 2026-11-08

## Scope

This diagnostic tested the local CaptureForge checkout at commit `1f2183b47d2306c6ec370fb1ab925fd938055d0e` against the original female and male Tripo GLBs. The original GLBs were not modified. The temporary fit meshes and Blender files are diagnostic outputs only.

CaptureForge reports GPL-3.0-or-later, Blender 4.4 LTS or newer, development on Blender 5.2, pure Python, headless-friendly functions, FaceForge auto-rig fitting, and a 26-bone lean facial rig with automatic distance-falloff weights. Its documented auto-fit convention requires a clear human-like face facing `-Y` with the character's left on `+X`.

## Coefficients

Command:

```powershell
& C:\Users\USER\captureforge\.venv\Scripts\python.exe scripts\report_captureforge_coefficients.py verification\captureforge-facial-rig-test\worried-reference.csv verification\captureforge-facial-rig-test\coefficient-report.json
```

Measured result: 121 frames, 51 numeric MediaPipe coefficients. `browInnerUp` varies from 0 to 0.19959 over the sequence, with 101 nonzero frames. MediaPipe does not emit the 52nd ARKit field `tongueOut`; this is expected by CaptureForge's README.

Expression coefficients: **VERIFIED**.

## Rig test

Command:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python scripts\run_captureforge_original_rig_test.py
```

The test used the same CaptureForge rig-builder and automatic weight functions on both characters. It canonicalized the input from existing Goal 1 face axes, isolated mesh components touched by CaptureForge anatomical landmarks, and used Goal 1 surface points only as an explicit fallback when CaptureForge's own render-to-MediaPipe pass failed.

| Check | Female | Male |
|---|---|---|
| CaptureForge fitted rig | FAIL | PASS: 26 bones generated |
| Render-to-MediaPipe auto-fit | FAIL: no face detected; Goal 1 source is `generated-rigged.glb`, tested input is `generated-original.glb`, and the derived face slab contains 0 vertices | FAIL: no face detected; Goal 1 surface fallback used |
| Actual original facial mesh visibly raises | FAIL | FAIL |
| Eyebrow landmark movement | Not evaluated because fit mesh was empty | approximately 0.0000016 source units at ID 70, 0.00000013 at ID 105 |
| New invalid coordinates | Not evaluated | 0 |
| Collapsed-triangle count | Not evaluated | 0; minimum area ratio 0.8769 |
| Textured renders | `female/neutral.png`, `female/raised.png` unavailable because fit stopped before rig creation | `male/neutral.png`, `male/raised.png` |

## Diagnosis

The expression coefficients are valid, and CaptureForge itself is available and headless-compatible. The facial rig was not visually validated on either original Tripo input.

The female failure is a concrete source-mesh correspondence blocker: the available Goal 1 attachment report was generated against `generated-rigged.glb`, not the tested `generated-original.glb`; none of the attachment-derived face vertices intersected the original input. The male fallback built 26 bones and preserved valid triangle coordinates, but the tested brow pose produced effectively zero eyebrow landmark movement and the neutral/raised renders are visually indistinguishable. CaptureForge's rig creation therefore does not constitute a successful expression transfer.

No permanent mesh or Goal 1 data was changed. The original GLBs remain untouched.

## Final status

FEMALE: **FAIL**

MALE: **FAIL**

EXPRESSION COEFFICIENTS: **VERIFIED**

FACIAL RIG: **FAILED** for this two-character test

VISUAL DEFORMATION: **FAIL**

OVERALL STEP RESULT: **FAILED**

Recommended next action: create or locate a Goal 1 attachment record produced from the exact female `generated-original.glb`, then independently validate CaptureForge's brow-control pose mapping on both models before attempting another expression test.
