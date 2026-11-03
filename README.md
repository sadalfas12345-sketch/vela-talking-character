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

The default is the Avaturn female GLB. Use **Import Character** to choose a Tripo or Meshy `.glb`. Vela inspects meshes, materials, textures, morph targets, and the humanoid rig, maps recognized ARKit/Oculus/Ready Player Me facial names, reports missing capabilities, and switches to an imported model only when TalkingHead's required pose bones and usable speech morphs are present. The character selector switches back to the original avatar.

Recognized mappings are applied in memory to the GLB scene before TalkingHead loads it. The original mesh geometry, material/texture objects, skin weights, and other morphs are retained. The app uses glTF's standard right-handed Y-up coordinates and TalkingHead's `scaleToHipsLevel` retargeting against its reference rig. Inspection/mapping metadata is cached in browser local storage by file name, size, and modification time.

Models without facial morph deformation are inspected but not activated or silently replaced. A jaw or eye bone cannot create accurate visemes. For these files, generate facial shape keys on the face mesh in Blender with a facial-rigging workflow such as Faceit, including `jawOpen`, both blink targets, and Oculus visemes or equivalent ARKit shapes; export as GLB and import again. Vela does not claim to generate missing face deformation. A valid model with only partial facial targets is also reported with its missing visemes, blink shapes, and expression targets.

The original Tripo GLB and its Mixamo body-rigged GLB remain preserved byte-for-byte under `assets/tripo/`. `vela-reference-faced.glb` is the derived TalkingHead version, with 29 actual shape-key deformations added to the original skinned mesh. See [the Tripo face conversion report](assets/tripo/README.md). Rebuild it without any Tripo API calls with Blender 5.x using `blender -b --python scripts/build_tripo_face_rig.py`.

Run the automated browser checks with `npm.cmd run test:import`. The Tripo-specific `npm.cmd run test:tripo-face` uploads the derived GLB into Vela, verifies facial vertex deformation, synthesizes a spoken line through the PC-side HeadTTS service, captures the canvas during a live viseme, samples live viseme/blink/expression channels, and checks mobile rendering. The original `npm.cmd run test:tripo` still confirms the two unconverted GLBs are accurately diagnosed and are not silently activated.

The browser renders imported GLB geometry locally. Heavy Kokoro inference stays on the RTX PC when the HeadTTS service is reachable; speech audio and timed visemes are then sent to the browser renderer. No webcam or body tracking is used.

The speech bridge is intentionally kept at the `head.speakAudio(message.data)` boundary. NVIDIA Audio2Face v3 can be added there later as another audio and facial-animation provider without replacing the UI or avatar lifecycle.
