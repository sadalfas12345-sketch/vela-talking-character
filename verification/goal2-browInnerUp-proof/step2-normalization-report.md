# Video-to-Tripo transfer Step 2

## Result

**20/20 — PASS.** All required synthetic normalization tests were executed.

## Measurements

- Neutral RMS displacement: 0.003167 interocular widths, threshold 0.005 — PASS, 5/5.
- Translation invariance maximum error: 7.55e-08, threshold 0.001 — PASS, 5/5.
- Rotation and scale invariance maximum error: 1.40e-07, threshold 0.001 — PASS, 5/5.
- Expression preservation maximum error: 9.93e-08, threshold 0.001; 100% of controlled expression landmarks within tolerance — PASS, 5/5.

The tests use similarity alignment over stable landmarks 33, 263, 1, and 152. Expression landmarks are not used to estimate the rigid transform. The complete numeric record is in `step2-normalization.json`.
