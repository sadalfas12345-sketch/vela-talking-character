# Tripo facial-rig verification frames

These images were captured from the real Vela WebGL scene by `scripts/verify_tripo_face_animation.mjs` using headless Chromium on November 3, 2026.

- `artifacts-tripo-neutral.png` — imported Tripo GLB at rest.
- `artifacts-tripo-neutral-canvas.png` — neutral raw WebGL canvas for comparison.
- `artifacts-tripo-speaking-canvas.png` — raw WebGL canvas captured while the HeadTTS timeline had `viseme_aa` at 0.406; the lower lip is visibly displaced during synthesized speech.
- `artifacts-tripo-speaking-frame.png` — full Vela interface during that speech run.
- `artifacts-tripo-jaw-open.png` — direct `jawOpen` geometry control at full weight.
- `artifacts-tripo-viseme-aa.png` — direct `viseme_aa` geometry control at full weight; this intentionally shows the limit of the closed oral surface.
- `artifacts-tripo-blink-left.png` and `artifacts-tripo-blink-right.png` — independent blink controls.
- `artifacts-tripo-smile-left.png`, `artifacts-tripo-frown-left.png`, and `artifacts-tripo-brow-up.png` — expression and brow controls.
- `artifacts-tripo-talking-desktop.png` and `artifacts-tripo-talking-mobile.png` — app after speech at 1280×900 and 412×915; mobile canvas matched the viewport.

The automated render comparison measured changed pixels against neutral for jaw 2,472; `viseme_aa` 3,624; left blink 1,743; right blink 2,421; smile 966; frown 768; brow 970. The speech request received HTTP 200 from local HeadTTS; live animation peaked at 0.761 across measured mouth channels, 1.0 for blink, and 0.355 for expression. The active `viseme_aa` value was 0.406 in the captured speaking frame. The browser reported no page errors. At full weight, a viseme can look distorted because the original mesh has no oral cavity; the captured live value shows a smaller surface lip movement.

These results verify actual skinned-vertex deformation, speech audio, and live viseme timing. Blink screenshots show closed eyelids versus the neutral open-eye frame. They do not imply that the closed mouth shell contains an anatomical oral cavity, teeth, or tongue.
