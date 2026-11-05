# Tripo avatar certification

**Overall: INCOMPLETE**

Tested commit: `7b1183de29552aa1d0a0da96b952d2b5c28d91c8`

No acceptance threshold was changed. UNVERIFIED is not a pass.

## Gate 1: Source asset integrity — PASS

The raw Tripo GLB and Mixamo GLB are unchanged. The facial GLB is an intentional derived asset and contains the converted rig.

Evidence: `verification/tripo-gate1-integrity.json`, `verification/tripo-gate1-renderer.json`, `verification/tripo-gate1-rigged-render.png`, `verification/tripo-gate1-faced-render.png`
## Gate 2: Body orientation and skeleton — PASS

All required body-axis, neutral-pose, root-adjusted mesh-to-skeleton displacement, and runtime camera measurements are within limits. The reported global Hips translation is recorded separately as the expected TalkingHead placement offset.

Evidence: `verification/tripo-gate2-orientation.json`, `verification/tripo-gate2-stage-e.json`, `verification/tripo-stage-e-desktop.png`, `verification/tripo-stage-e-mobile.png`
## Gate 3: Facial landmark and morph geometry — UNVERIFIED

Landmark hits do not establish that each ray landed on the correct visible anatomical feature. Independent feature projection and neutral-drift measurements are missing.

Action: Annotate visible eye, lip, brow, and chin features independently on the source render, then compare those measurements to the registered markers and quantify neutral deformation.

Evidence: `assets/tripo/vela-photoreal/facial-rig-report.json`, `verification/tripo-stage-e-landmark-overlay.png`, `verification/tripo-stage-e-landmark-overlay.json`
## Gate 4: Speech shape quality — UNVERIFIED

Stopped after Gate 3 UNVERIFIED.

Action: Complete Gate 3, then rerun this runner so downstream gates execute in order.

Evidence: Not captured.
## Gate 5: Adapter and animation channels — UNVERIFIED

Stopped after Gate 3 UNVERIFIED.

Action: Complete Gate 3, then rerun this runner so downstream gates execute in order.

Evidence: Not captured.
## Gate 6: Live speech synchronization — UNVERIFIED

Stopped after Gate 3 UNVERIFIED.

Action: Complete Gate 3, then rerun this runner so downstream gates execute in order.

Evidence: Not captured.
## Gate 7: Camera, presentation, and rendering — UNVERIFIED

Stopped after Gate 3 UNVERIFIED.

Action: Complete Gate 3, then rerun this runner so downstream gates execute in order.

Evidence: Not captured.
## Gate 8: End-to-end stability and performance — UNVERIFIED

Stopped after Gate 3 UNVERIFIED.

Action: Complete Gate 3, then rerun this runner so downstream gates execute in order.

Evidence: Not captured.
## Gate 9: Perceptual demo acceptance — UNVERIFIED

Stopped after Gate 3 UNVERIFIED.

Action: Complete Gate 3, then rerun this runner so downstream gates execute in order.

Evidence: Not captured.

## Scope notes

Android rendering and performance were not tested on physical Android hardware. The source Tripo and Mixamo GLBs were preserved; the facial derivative is intentional.
