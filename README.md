# Vela talking character demo

Browser-based talking character demo built from pinned upstream TalkingHead and HeadTTS submodules. The browser renders the avatar locally; HeadTTS Kokoro inference prefers the PC-side REST service and falls back to browser WebGPU/WASM.

## Run

From this directory, use two terminals:

Terminal 1 runs local Kokoro on the PC:

```powershell
npm.cmd run tts
```

Terminal 2 serves Vela to the local network and Tailscale:

```powershell
npm.cmd run serve
```

Open `http://<PC-Tailscale-IP>:4174` from an Android phone connected to the same Tailscale tailnet. The Vela server proxies `/v1` requests to HeadTTS on the PC, so the phone only needs access to port `4174` and Kokoro inference stays on the RTX PC. Browser WebGPU/WASM remains the fallback.

Clone with upstream source included:

```bash
git clone --recurse-submodules https://github.com/sadalfas12345-sketch/vela-talking-character.git
```

Install HeadTTS dependencies on Windows with `npm.cmd install --ignore-scripts` from `HeadTTS`, since its upstream postinstall uses a Unix-only `mkdir` command. Then run the two commands above from this repository root.

## Verified

The default is the Avaturn female GLB. Choose **Tripo · portrait** in the character selector to load the generated character directly from this PC, or use **Import Character** for a Tripo or Meshy `.glb`. Vela inspects meshes, materials, textures, morph targets, and the humanoid rig, maps recognized ARKit/Oculus/Ready Player Me facial names, reports missing capabilities, and switches to an imported model only when TalkingHead's required pose bones and usable speech morphs are present. The character selector switches back to the original avatar.

Recognized mappings are applied in memory to the GLB scene before TalkingHead loads it. The original mesh geometry, material/texture objects, skin weights, and other morphs are retained. The app uses glTF's standard right-handed Y-up coordinates and TalkingHead's `scaleToHipsLevel` retargeting against its reference rig. Inspection/mapping metadata is cached in browser local storage by file name, size, and modification time.

Models without facial morph deformation are inspected but not activated or silently replaced. A jaw or eye bone cannot create accurate visemes. For these files, generate facial shape keys on the face mesh in Blender with a facial-rigging workflow such as Faceit, including `jawOpen`, both blink targets, and Oculus visemes or equivalent ARKit shapes; export as GLB and import again. Vela does not claim to generate missing face deformation. A valid model with only partial facial targets is also reported with its missing visemes, blink shapes, and expression targets.

The generated character is preserved at `assets/tripo/vela-photoreal/generated-original.glb`, and its Mixamo-rigged version at `assets/tripo/vela-photoreal/generated-rigged.glb`. The Vela-ready derivative is `vela-photoreal-faced.glb`. It has 29 measured facial shape keys plus a small viseme-driven inner-mouth surface, while retaining the 4K PBR maps and 65-bone Mixamo skin. The derivative is reduced to 318,094 vertices and 583,172 triangles for practical browser use; both source GLBs remain unchanged. See [the character conversion report](assets/tripo/vela-photoreal/README.md). Rebuild without Tripo API calls using Blender 5.x and the committed landmark data: `blender -b --python scripts/build_tripo_photoreal_face_rig.py`.

Run browser checks with `npm.cmd run test:import` for the original avatar, compatible import, missing-morph diagnosis, and malformed-file handling. `npm.cmd run test:tripo-photoreal` imports the generated character, verifies real geometry changes for jaw, both blinks, smile, frown, and brows, sends spoken text through HeadTTS, captures a frame during an active viseme, samples live viseme/blink/expression channels, and checks phone-sized rendering. `npm.cmd run test:tripo` confirms the untouched Tripo GLBs without facial morphs are reported accurately and are not silently activated.

The browser renders imported GLB geometry locally. Heavy Kokoro inference stays on the RTX PC when the HeadTTS service is reachable; speech audio and timed visemes are then sent to the browser renderer. No webcam or body tracking is used.

The speech bridge is intentionally kept at the `head.speakAudio(message.data)` boundary. NVIDIA Audio2Face v3 can be added there later as another audio and facial-animation provider without replacing the UI or avatar lifecycle.

## Generate a Tripo character

Set `TRIPO_API_KEY` in the shell environment. `.env` files and secret files are ignored by Git. Then run `npm.cmd run generate:tripo`. The one-shot script checks the available balance, uploads `assets/tripo/vela-photoreal/reference-image.png`, submits one H3.1 image-to-model task with detailed geometry and texture, polls the returned task, and downloads `assets/tripo/vela-photoreal/generated-original.glb`. It records the task and estimate in `generation.json` and refuses to submit another paid generation over that manifest. The script never prints or saves the API key.

The current official Tripo docs list this configuration at an estimate of 60 credits: 40 for H3.1 image-to-3D with detailed texture and 20 for detailed geometry. Verify current pricing and account balance before running it. A generation request cannot accept a free-form text prompt in the documented image endpoint, so the supplied face reference is first prepared as a single clean image with the requested hair, eyes, outfit, and neutral pose.

The existing generated shell did not include a jaw cavity, separate teeth or tongue, eye meshes, eye bones, or facial blendshapes. The character-specific adapter registers 478 MediaPipe face landmarks against a matching Blender camera and builds actual mesh deformations on the measured face surface. It provides jaw/mouth movement, all 15 Oculus viseme names, independent eyelid closures, smile/frown, and brow controls. A 24-sided dark inner-mouth proxy is shape-keyed to the speech visemes so opening reads on screen; it contains no teeth or tongue. Since the eyes are baked into the single head surface, blink controls deform that surface and independent eyeball gaze is unavailable. Lip opening cannot produce anatomical mouth interiors. These limits are stated in `facial-rig-report.json`.
