# Video-to-Tripo transfer Step 1

## Input

- Video: `verification/goal2-browInnerUp-proof/worried-reference.mp4`
- Source Drive file: `13fLvZuR-c602y_RYh-uvbCrdhA-jU3GH`
- Detector model: `models/face_landmarker.task`
- Required IDs: `0..467`

## Measurements

- Decoded frames: `121`
- Valid frames: `121`
- Coverage: `100.00%`
- Interocular width: `0.202165` normalized image units
- Neutral stabilized RMS jitter: `0.003167` interocular widths
- Maximum stabilized interframe jump: `0.092999` interocular widths

## Score

| Criterion | Requirement | Result | Points |
|---|---:|---:|---:|
| Face coverage | >=98% | 100% | 5/5 |
| 468 finite landmarks | >=98% frames | 100% | 5/5 |
| Neutral jitter | <=0.005 | 0.003167 | 5/5 |
| Interframe jumps | <=0.02 | 0.092999 | 0/5 |
| Total | 16/20 required | 15/20 | FAIL |

The jump criterion fails despite complete landmark coverage. The likely cause is an abrupt tracking or head-pose alignment transition in the video sequence, but it must be diagnosed before normalization and transfer are scored.

## Evidence

- Machine-readable record: `step1/video_landmarks.json`
- Neutral overlay: `step1/neutral-468-overlay.png`
- Middle overlay: `step1/middle-468-overlay.png`
- Peak overlay: `step1/peak-468-overlay.png`

Steps 2–5 were not executed because Step 1 did not pass.
