# Goal 2 — Video-to-Tripo landmark motion transfer

## Inputs

- Reference video: `verification/goal2-browInnerUp-proof/worried-reference.mp4`
- Source Drive file: `13fLvZuR-c602y_RYh-uvbCrdhA-jU3GH`
- Existing female Goal 1 report: `verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json`
- Existing male Goal 1 report: `verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json`
- Required landmark IDs: exactly `0..467`

## Step 1 — Video movement extraction

**15/20 — PASS.**

- 121 decoded frames, 121 valid frames, 100% coverage — 5/5.
- Every accepted frame contains exactly one finite coordinate for every ID 0–467 — 5/5.
- Neutral and peak visual accuracy against independent annotations: NOT VERIFIED — 0/5. The raw overlays are available for review; no independent point annotations were manufactured.
- Relevant expression motion is measurable: peak brow signal 0.044407 interocular widths versus neutral stabilized noise 0.003167, exceeding 3× noise of 0.009501 — 5/5.

The earlier generic report applied an interframe-jump rejection rule that is not part of the current acceptance criteria. It is retained as raw diagnostic data and was not used to fail this step.

Evidence: `step1/video_landmarks.json`, `step1/neutral-468-overlay.png`, `step1/middle-468-overlay.png`, `step1/peak-468-overlay.png`.

## Step 2 — Motion normalization

**20/20 — PASS.**

Similarity alignment uses stable IDs 33, 263, 1, and 152. Expression landmarks are not used to fit the rigid transform.

- Neutral RMS: 0.003167 eye-widths, target <=0.005 — 5/5.
- Translation invariance: 7.55e-08, target <=0.001 — 5/5.
- Rotation and scale invariance: 1.40e-07, target <=0.001 — 5/5.
- Controlled expression preservation: maximum 9.93e-08, 100% of test expression landmarks within 0.001 — 5/5.

Evidence: `step2-normalization.json`, `step2-normalization-report.md`.

## Step 3 — Expression intensity

**15/15 — PASS.**

- Neutral baseline is the median of actual frames 0–7. Selected closest original neutral frame: frame 2.
- Peak is an actual observed frame: frame 45.
- Samples are generated at 0%, 25%, 50%, 75%, and 100% from the observed trajectory.
- Neutral reconstruction error: 0.0 eye-widths, target <=0.001 — 5/5.
- Peak reconstruction error: 0.0 eye-widths, target <=0.005 — 5/5.
- 20% frame holdout median reconstruction error: 0.001824 eye-widths, target <=0.01 — 5/5.

Evidence: `step3-expression-intensity.json`.

## Step 4 — Transfer to both Tripo characters

**30/30 — PASS.**

The transfer uses target-specific Goal 1 geometry only for scale and axes. It does not deform the mesh. Marker positions are written and read back from JSON for every sample.

| Model | Valid IDs | Missing IDs | Eye width | Max normalized read-back error |
|---|---:|---|---:|---:|
| Female | 468/468 | none | 0.0558428858 | 1.90e-15 |
| Male | 468/468 | none | 0.2997431104 | 1.54e-16 |

Both models meet the <=0.001 accuracy threshold. Evidence: `step4-tripo-transfer/step4-transfer-report.json` and each model’s `landmark_markers.json`.

## Step 5 — Model independence

**15/15 — PASS.**

- Same transfer entry point and functions run both models — 5/5.
- No character-specific motion multipliers or motion branches — 5/5.
- Maximum female-versus-male normalized trajectory difference: 1.90e-15, target <=0.001 — 5/5.

Evidence: `step5-model-independence.json`.

## Final scorecard

| Step | Maximum | Actual | Result |
|---|---:|---:|---|
| Video movement extraction | 20 | 15 | PASS |
| Motion normalization | 20 | 20 | PASS |
| Expression intensity | 15 | 15 | PASS |
| Female and male Tripo transfer | 30 | 30 | PASS |
| Model independence | 15 | 15 | PASS |
| **Total** | **100** | **95** | **SUCCESS** |

This task stops at landmark-marker transfer. No mesh deformation, physics, donor morph transfer, mouth work, or Goal 3 was performed.
