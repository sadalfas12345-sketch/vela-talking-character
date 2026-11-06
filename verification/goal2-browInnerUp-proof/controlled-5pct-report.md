# Goal 2 controlled 5% solver test

The Avaturn donor was bypassed. For each model, every verified brow attachment
was prescribed an upward displacement equal to 5% of that model's measured
interocular distance in the Goal-1 anatomical-up frame.

| Model | Requested brow | Achieved brow | Eyelid movement | New inversions | Visual |
|---|---:|---:|---:|---:|---|
| Female | 2.792 mm | 3.624 mm max after reimport | 0 mm | 27 | FAIL |
| Male | 14.987 mm | 18.561 mm max after reimport | 0 mm | 35 | FAIL |

The pre-export stages show the defect directly. Before correction, both models
reach 100% of the prescribed barycentric displacement. The geometric correction
reduces the female anchors to 0.243–1.649 mm and the male anchors to 0.508–1.111
mm. Re-enforcing the hard constraints restores 100% displacement but leaves 27
female and 35 male inverted triangles. Thus the current iterative smoothing and
vertex-halving method cannot satisfy hard brow constraints and zero inversions
simultaneously.

The reimported nearest-surface measurement is only a diagnostic fallback for
vertex-reordered GLBs. The source-stage barycentric values are the authoritative
constraint test; neither model meets the required 90% constraint criterion with
zero inversions.

Codex vision inspection found a visible local brow artifact on the female and no
convincing bilateral eyebrow raise on the male. Neutral identity is not enough
to pass this controlled test.

Failing stage: constrained deformation optimization after geometric correction.
The next implementation must use a true constrained optimization that includes
triangle-quality constraints while preserving the brow barycentric constraints;
no expression-strength reduction or character-specific offset is accepted.

Goal 3 was not started.
