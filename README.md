# Vela talking character demo

Browser-based talking character demo built from pinned upstream TalkingHead and HeadTTS submodules. The browser renders the avatar locally; HeadTTS Kokoro inference prefers the PC-side REST service and falls back to browser WebGPU/WASM.

## Run

From this directory:

```powershell
npm.cmd run tts
npm.cmd run serve
```

Open `http://100.116.192.77:4174` from an Android phone connected to the same Tailscale tailnet. The TTS endpoint is exposed on port `8882` and is preferred by the browser, so Kokoro inference stays on the RTX PC when reachable. Browser WebGPU/WASM remains the fallback.

Clone with upstream source included:

```bash
git clone --recurse-submodules https://github.com/sadalfas12345-sketch/vela-talking-character.git
```

Install HeadTTS dependencies on Windows with `npm.cmd install --ignore-scripts` from `HeadTTS`, since its upstream postinstall uses a Unix-only `mkdir` command. Then run the two commands above from this repository root.

## Verified

- Julia avatar loads from `HeadTTS/avatars/julia.glb`.
- Runtime inspection found 83 scene nodes, 10 meshes, and 288 facial morph targets.
- Oculus visemes including `viseme_aa`, `viseme_E`, `viseme_I`, `viseme_O`, `viseme_U`, `viseme_PP`, and `viseme_SS` are present.
- HeadTTS returned Kokoro audio with word and viseme timestamps to TalkingHead.
- Chromium Playwright smoke test passed at desktop and 412px phone viewport.
- No webcam, FaceVerse, or body tracking is used.

The speech bridge is intentionally kept at the `head.speakAudio(message.data)` boundary. NVIDIA Audio2Face v3 can be added there later as another audio and facial-animation provider without replacing the UI or avatar lifecycle.
