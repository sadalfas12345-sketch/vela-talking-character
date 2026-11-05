# Vela Tripo face repair handoff

## Workspace

- Repository: `C:\Users\USER\talking-character-demo`
- Last committed revision: `7b1183de29552aa1d0a0da96b952d2b5c28d91c8` (`Add sequential Tripo avatar certification`)
- Working tree has many staged and unstaged changes. Preserve them; inspect `git status --short` before staging anything.
- `HeadTTS` is a modified submodule. Do not stage it accidentally. `tmp-upper.png` is unrelated.

## Completed evidence

- Original Tripo GLBs remain at `assets/tripo/vela-photoreal/generated-original.glb` and `generated-rigged.glb`.
- Existing-shell Gate 4 failure and structural comparison: `verification/tripo-mouth-structure-decision.md`, `verification/tripo-gate4-measurements.json`, `verification/tripo-mouth-bvh-overlap.json`.
- Full-head transfer prototype: `assets/tripo/vela-photoreal/intermediates/vela-fullhead-expanded-prototype.glb`.
- Runtime captures: `verification/tripo-fullhead-expanded-runtime-final/`.
- Runtime assessment: `verification/tripo-fullhead-expanded-runtime-final/assessment.md`.
- Latest explicit Playwright run completed: default Avaturn loaded; full-head prototype activated; HeadTTS HTTP 200; live viseme_E influence 0.6865 while `isSpeaking`; blink and expression morphs altered rendered pixels; zero page errors. Mobile was only Chromium viewport emulation.
- Visual inspection found pale jagged jaw and temple cut edges and a bad neck transition. Candidate fails visual acceptance. No claim of complete temporal synchronization was made.

## Diagnosis and next action

The current builder cuts only a front oval from the Tripo shell (`scripts/build_tripo_full_face_transfer.py`) but keeps and projects a full donor head. The remaining Tripo shell intersects or peeks around the fitted donor boundary, producing visible pale fragments. The previous landmark aperture method is invalid for the fitted donor because its mapped donor points do not track visible lip contours.

Next: keep the original Tripo facial vertices as the deformation target. Transfer Avaturn neutral-to-expression motion mathematically onto those vertices, independently validate the 3D correspondence, and use the resulting proof to identify the closed-mouth topology failure. If the mouth cannot form a real aperture, perform only localized surgery around the upper/lower lip boundary and recessed oral cavity. Do not replace the face, cut the forehead/temples/neck, widen donor boundaries, resize donor teeth, or reuse invalid donor-patch aperture measurements. Preserve original assets.

## Current limitations

- Gate 1 and Gate 2 are recorded PASS for the previously certified facial derivative; check those artifacts against current files before reusing the status.
- Gate 3 remains UNVERIFIED.
- Existing Tripo shell Gate 4 is FAILED. Full-head prototype also has visible integration defects and is not a Gate 4 pass.
- Gates 5–9 are not certified. No physical Android performance test, three-sample sync test, 10-run stability test, or continuous perceptual review is complete.
- Do not commit or push until changes are coherent and reviewable. Before any commit, global `AGENTS.md` requires a concise Gmail summary to `indraxulix@gmail.com` immediately after commit; check connected email capability first.
- Do not spend Tripo credits or regenerate the character.
- The full-face and donor-hull replacement experiments are FAILED/ABANDONED. They are retained only as negative evidence and are not part of the required architecture.
