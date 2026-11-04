# Tripo avatar certification

**Overall: FAILED**

Tested commit: `672912e887067525046ed58a9bf65bdb94522832`

This run is sequential and stops after the first failed gate. No threshold was changed.

## Gate 1: Structural integrity and rendered skinning - PASS

The preserved raw Tripo source is intentionally unrigged; checks for animation structure are applied to the Mixamo rig and facial derivative. Both rendered successfully.

Evidence: `verification/tripo-gate1-integrity.json`, `verification/tripo-gate1-renderer.json`, `verification/tripo-gate1-rigged-render.png`, `verification/tripo-gate1-faced-render.png`
## Gate 2: Orientation and preprocessing stages A-E - FAIL

The generated Mixamo rest pose has its head forward axis 18.30 degrees from hips and up to 13.68 degrees spine roll, exceeding limits. Applying the adapter yaw rotates the character root but does not correct this internal head/neck rest-pose mismatch. Stage E is not measured.

Action: Correct the source rest pose or adapter bone-local rest transforms, then verify camera-facing stage E and rerun downstream gates.

Evidence: `verification/tripo-gate2-orientation.json`
## Gate 3: Independent facial landmarks and neutral deformation - UNVERIFIED

Stopped after Gate 2 FAIL.

Action: Complete Gate 2 corrective action, then rerun this sequential certification.

Evidence: Not captured.
## Gate 4: Measured speech shapes and eye/expression deformations - UNVERIFIED

Stopped after Gate 2 FAIL.

Action: Complete Gate 2 corrective action, then rerun this sequential certification.

Evidence: Not captured.
## Gate 5: HeadTTS-to-TalkingHead channel mapping - UNVERIFIED

Stopped after Gate 2 FAIL.

Action: Complete Gate 2 corrective action, then rerun this sequential certification.

Evidence: Not captured.
## Gate 6: Live audio and lip synchronization - UNVERIFIED

Stopped after Gate 2 FAIL.

Action: Complete Gate 2 corrective action, then rerun this sequential certification.

Evidence: Not captured.
## Gate 7: Desktop and mobile camera framing - UNVERIFIED

Stopped after Gate 2 FAIL.

Action: Complete Gate 2 corrective action, then rerun this sequential certification.

Evidence: Not captured.
## Gate 8: Ten-cycle sustained performance and Android device check - UNVERIFIED

Stopped after Gate 2 FAIL.

Action: Complete Gate 2 corrective action, then rerun this sequential certification.

Evidence: Not captured.
## Gate 9: Continuous demo and human visual quality rubric - UNVERIFIED

Stopped after Gate 2 FAIL.

Action: Complete Gate 2 corrective action, then rerun this sequential certification.

Evidence: Not captured.

## Scope notes

The Android hardware performance requirement is not certifiable from this PC because no Android device/ADB connection is available. It is not reported as passed.
The Tripo source GLBs were not regenerated or modified by this certification.
