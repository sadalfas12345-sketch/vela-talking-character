# Full-head Tripo transfer runtime check

Tested commit: `7b1183de29552aa1d0a0da96b952d2b5c28d91c8`

## Runtime evidence

- Headless Playwright loaded the default Avaturn avatar, imported `vela-fullhead-expanded-prototype.glb`, and activated the Tripo selection without browser exceptions.
- HeadTTS returned HTTP 200. The Web Audio context was running and the character entered `isSpeaking` while the test sampled a live `viseme_E` influence of `0.6865` at 1,879.6 ms after synthesis playback was requested. The sampled influence is live runtime evidence; this single sample is not an onset-accuracy or full-duration synchronization measurement.
- The imported scene reports 7 meshes, 7 materials, 11 textures, 65 bones and 72 morph targets. TalkingHead detected 15/15 speech channels, 2/2 blink channels and 7 expression channels.
- Direct full-influence controls changed rendered pixels for `jawOpen`, `viseme_aa`, both blink channels, smile, frown and brow movement.
- The test rendered a 412×915 mobile-sized Chromium viewport. This is viewport coverage, not a physical Android performance test.
- Browser page-error count: 0.

## Visual inspection of rendered frames

Inspected `neutral.png`, `jaw-open.png`, `blink-left.png` and `speaking-canvas.png` from this run. The open-mouth frame shows a large dark oral opening with teeth and tongue visible. The unilateral blink frame visibly closes one eye. The speech capture shows an open mouth during the active speech sample.

The candidate has conspicuous facial integration defects: jagged pale cut edges under the jaw and at the temples, an uneven neck junction, and visible gaps where the fitted head meets retained Tripo geometry. These are not acceptable for the Gate 4 no-visible-intersection requirement or Gate 9 perceptual acceptance. The candidate therefore is not certified, despite functioning speech and morph channels.

## Decision

Do not continue widening the mouth, scaling teeth, or adjusting these same fitted boundaries by eye. The current full-head transfer is a useful articulation proof but fails as an integrated appearance. Gate 4 remains failed for the original Tripo facial shell based on the recorded aperture and dental-intersection measurements. This full-head candidate has not passed Gate 4: visible integration defects are sufficient to fail, and its landmark-aperture measurements are invalid because the mapped donor points do not identify the visible lip contours.

Keep the original and Mixamo source GLBs unchanged. The next structural attempt must improve the facial-region boundary using topology-aware fitting or a larger fitted head region while retaining the original face/hair appearance; it must be separately measured and visually inspected before it can replace the working default.
