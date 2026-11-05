# Goal 1 MVP facial landmark detection

Automated evaluation only. No manual review or contaminated reference points
were used. The 30-point set contains 8 lip points, 8 eyelid points, 5 nose
points, 3 chin or jaw points, and 6 eyebrow points.

Correctness for this MVP means: the standardized MediaPipe landmark identity is
present in the inspected frontal overlay and its corrected-camera raycast hits a
first-visible, front-facing triangle on the original GLB. This is not an
independent anatomical certification.

| Character | Correct landmarks | Lips | Eyelids | Valid 3D attachments | Overall |
|---|---:|---:|---:|---:|---|
| Female Tripo | 30 / 30 | 8 / 8 | 8 / 8 | 30 / 30 | PASS |
| Male Tripo | 30 / 30 | 8 / 8 | 8 / 8 | 30 / 30 | PASS |

Acceptance threshold: at least 24/30 overall, at least 80% lips, and at least
80% eyelids. Both characters pass the automated MVP threshold.

Evidence:

- Female neutral: `cross-character-accuracy/female/refined-neutral.png`
- Female landmarks: `cross-character-accuracy/female/refined/frontal-landmarks.png`
- Female 3D attachments: `cross-character-accuracy/female/oblique-3d-attachments.png`
- Male neutral: `cross-character-accuracy/male/refined-neutral.png`
- Male landmarks: `cross-character-accuracy/male/refined/frontal-landmarks.png`
- Male 3D attachments: `cross-character-accuracy/male/oblique-3d-attachments.png`

Known limitation: this MVP pass does not certify hidden or partially obscured
male upper-lip anatomy and does not replace independent human annotation.
No expression transfer, registration, mouth reconstruction, or animation was
performed.
