# Video-to-Tripo transfer Step 1

## Result

**15/20 — PASS under the current acceptance rule.** The required coverage and landmark-ID integrity conditions pass. The visual-reference criterion is not independently verified, so it earns zero. The expression-motion criterion is measured from the extracted sequence and passes.

## Measurements

- Input: `verification/goal2-browInnerUp-proof/worried-reference.mp4`
- Decoded frames: 121
- Valid frames: 121
- Coverage: 100.00% — 5/5
- Landmark IDs: exactly 0..467 in every accepted frame — 5/5
- Neutral stabilized RMS noise: 0.003167 interocular widths
- Relevant brow peak displacement: 0.044407 interocular widths
- Three-times-noise threshold: 0.009501 interocular widths
- Meaningful expression movement: PASS — 5/5
- Neutral/peak visual accuracy against independently annotated points: NOT VERIFIED — 0/5

The earlier generic script reported `pass=false` because it applied an interframe-jump rule that is not part of the current Step 1 acceptance criteria. The raw sequence and overlays are preserved.

## Evidence

- Machine-readable sequence: `step1/video_landmarks.json`
- Neutral overlay: `step1/neutral-468-overlay.png`
- Middle overlay: `step1/middle-468-overlay.png`
- Peak overlay: `step1/peak-468-overlay.png`
