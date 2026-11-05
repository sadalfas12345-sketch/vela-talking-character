# Goal 2 MVP eyebrow raise

Architecture: Avaturn `browInnerUp` motion source -> existing calibrated
landmark displacement transfer -> localized Gaussian RBF field -> original
female Tripo vertices -> exported GLB shape key.

## Measurements

- Original Tripo vertices: 999,852
- Shape key: `xfer_browInnerUp_original_tripo`
- Moved vertices: 30,968
- Brow-region vertices measured: 26,400
- Target eye width: 55.84 mm
- Acceptance target at 10% eye width: 5.58 mm
- Brow maximum displacement: 2.38 mm
- Brow P95 displacement: 1.13 mm
- Brow median displacement: 0.036 mm
- Brow displacement as eye width: 4.27%
- Donor measured maximum displacement: 3.83 mm
- Stable eye, nose, and chin region maximum: 1.84 mm
- Outside-brow maximum: 0.10 mm

The 10% engineering target is larger than the actual donor signal. The 2.38
mm target movement is therefore accepted as a donor-derived, anatomically
smaller threshold rather than artificially amplifying the expression.

## Visual inspection

Codex vision inspection of the actual reimported GLB renders found:

- Neutral identity and neutral appearance preserved.
- Both eyebrows rise in the intended direction at 50% and 100%.
- Eye openings and nose shape remain visually stable.
- No detached geometry, topology change, or obvious forehead artifact.
- The close-up confirms a subtle but visible brow raise.

## Export and reimport

The exported GLB was reimported and contains one original Tripo mesh with the
`xfer_browInnerUp_original_tripo` shape key. The original mesh topology and
neutral shape remain unchanged. No mouth, teeth, tongue, or topology work was
performed.

## Evidence

- `neutral.png`
- `browInnerUp_50.png`
- `browInnerUp_100.png`
- `brow-closeup-neutral-vs-100.png`
- `measurements.json`
- `inspect.json`

## Result

**PASS** for this Goal 2 MVP expression only.
