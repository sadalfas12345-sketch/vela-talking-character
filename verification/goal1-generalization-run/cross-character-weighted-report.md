# Goal 1 cross-character generalization: first run

## Baseline

- Branch: `wip/tripo-face-repair`
- Baseline commit before generation: `ca3e9a7982a2fd270e62c745c9509d9fa757e51a7`
- Existing Goal 1 entry point: `scripts/onboard_goal1_model.py`
- Existing Tripo detector and attachment code were not changed before the first-run test.
- Original female GLB was preserved.

## Generation

The Drive reference was downloaded and its front natural panel was extracted to `verification/goal1-generalization-reference-front.png`.

Exactly one Tripo task was submitted:

- Task: `282c7782-479e-4c50-8808-1a2c3cdb2977`
- Model: `v3.1-20260211`
- Estimated cost: 60 credits
- Available before task: 320 credits
- Estimated remainder: 260 credits
- Status: success
- Output: `assets/tripo/generalization-male-20261105/generated-original.glb`
- Download size: 66,697,216 bytes
- Generation manifest: `assets/tripo/generalization-male-20261105/generation.json`

The original female Tripo assets were not overwritten. No rigging call was made.

## Zero-customization first run

The same command and source code were run on both models:

```powershell
python scripts/onboard_goal1_model.py <model.glb> <output-directory>
```

Female result:

- GLB inspection: PASS
- 478 detector landmarks were available from the existing calibrated evidence package.
- 476 valid visible-surface hits.
- 29 deterministic selected attachments.
- 1 selected unresolved landmark.
- Independent anatomy: UNVERIFIED.

Male result:

- GLB inspection: PASS.
- Mesh inventory: 1 mesh, 991,219 vertices, 1 node, no skins, no cameras.
- Head metadata: ambiguous; no head or facial skeleton metadata was present.
- Automatic orientation: UNVERIFIED.
- Automatic calibrated render: not reached.
- MediaPipe detection: not reached.
- 3D projection and barycentric attachment: not reached.

The first failing stage for the new male is automatic head and facial orientation calibration from the GLB. The current implementation correctly stopped rather than supplying the female Tripo camera or manually calibrated coordinates.

## Weighted anatomical scoring

Rubric: lips and mouth 30, eyes and eyelids 25, nose 15, jaw and chin 10, eyebrows 10, remaining landmarks 10.

Correctness tolerance used for the provisional female score:

- 2D error at or below each point's explicitly recorded `manualUncertaintyPixels`.
- Front-facing first-visible surface hit.
- Oblique first-surface visibility.
- No unresolved point or incorrect anatomical region.

The reference set has one visual reviewer and is not independent ground truth. Therefore all numerical scores below are **PROVISIONAL**, not certified.

Female provisional regional results:

| Region | Weight | Evaluated | Correct | Incorrect | Occluded | Unresolved | Provisional points |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lips and mouth | 30 | 10 | 3 | 7 | 0 | 0 | 9.00 |
| Eyes and eyelids | 25 | 12 | 7 | 2 | 3 | 0 | 14.58 |
| Nose | 15 | 5 | 4 | 1 | 0 | 0 | 12.00 |
| Jaw and chin | 10 | 3 | 2 | 0 | 0 | 1 | 6.67 |
| Eyebrows | 10 | 0 | 0 | 0 | 0 | 0 | UNREVIEWED |
| Remaining | 10 | 0 | 0 | 0 | 0 | 0 | UNREVIEWED |

The evaluated regions cover 80/100 rubric points. Their provisional normalized score is **52.81/100**. A certified overall score cannot be calculated because the references are not independently reviewed and eyebrows plus remaining landmarks are unreviewed.

The lips score is 9/30, below the required 80% regional threshold. The eyes and eyelids score is 14.58/25, also below the required 80% regional threshold.

Male weighted score: **UNVERIFIED**. No landmarks or independent references were available because the first-run pipeline stopped before calibrated rendering and detection.

## Raw first-run evidence

- [Female onboarding report](female/goal1-onboarding-report.json)
- [Male onboarding report](male/goal1-onboarding-report.json)
- [Female weighted score](female/goal1-weighted-anatomical-score.json)
- [Male generation manifest](../../assets/tripo/generalization-male-20261105/generation.json)
- [Extracted reference front panel](../goal1-generalization-reference-front.png)

No male neutral render, landmark overlay, or 3D attachment image was generated because the first-run onboarding failed before calibrated rendering. No evidence was hidden or replaced with a manually calibrated result.

## Decision

The pipeline did generalize to GLB inventory inspection, but it did not generalize to automatic head orientation, calibrated rendering, landmark detection, or attachment for the new unrigged male. Goal 1 stops here. No deformation, mouth work, teeth, speech, or Goal 2 work was started.
