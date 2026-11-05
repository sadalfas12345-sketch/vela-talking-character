# Original Tripo fitted-surface motion transfer assessment

Status: **PARTIAL SUCCESS / GATE 3 STILL UNVERIFIED**

The fitted Avaturn surface cache was used as a motion source only. Displacement
was transferred by Gaussian nearest-surface interpolation onto the original
Tripo vertices. No Avaturn geometry was exported.

## Results

- `eyeBlinkLeft`: visible left-eyelid closure in
  `verification/vela-original-tripo-eyeBlinkLeft-surface-transfer-render/jawOpenTransfer.png`.
  Original Tripo mesh and identity remain present.
- `jawOpen`: severe mouth collapse and surface artifacts in
  `verification/vela-original-tripo-jawOpen-surface-transfer-render/jawOpenTransfer.png`.
- `viseme_PP`: visually near-neutral and not independently accepted.
- `viseme_O`: visible pucker, but not a valid oral opening.

## Diagnosis

The eye region has usable surface correspondence even though eyelid landmark
positions remain static. The closed Tripo mouth does not have a valid
upper/lower lip surface correspondence for direct nearest-surface transfer;
mouth motion therefore collapses or crosses the shell. This confirms the need
for localized lip-boundary surgery before using surface motion transfer for
speech channels.

The surface-transfer path is retained for eyelid and other regions with
validated surface correspondence. It is not accepted as a mouth solver.
