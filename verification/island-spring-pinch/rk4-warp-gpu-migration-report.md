# VELA GPU RK4 migration

Generated from the original Tripo spring fixtures on branch `wip/tripo-face-repair`.

## Scope

The existing Hookean model is unchanged:

- original source vertex IDs and triangle connectivity;
- one spring for every unique original triangle edge;
- area-derived per-vertex masses;
- fixed inner-anchor springs;
- damping, gravity, and the barycentric pinch controller;
- RK4 integration and the existing Tripo coordinate conversion.

No cross-island springs, welding, remeshing, stretch caps, force clipping, or post-processing were added.

## GPU environment

- GPU: NVIDIA GeForce RTX 2060 with Max-Q Design, 6 GB
- Driver: 592.82
- Installed CUDA compiler: 12.4
- Warp: 1.19.0, CUDA device `cuda:0`, `sm_75`
- CPU reference: existing Node Float64 equations exported through `--export-gpu-cpu-references`
- GPU arithmetic: Warp Float32, with explicit CPU Float64 comparison

PyTorch was present only as `2.13.0+cpu`; it was not used. Warp was installed from `warp-lang==1.19.0`.

## GPU implementation

`scripts/rk4_warp_gpu.py` keeps positions, velocities, RK4 stages, spring CSR adjacency, anchors, and pinch state on the GPU for the complete run. The force kernel gathers incident surface springs per vertex, gathers support springs per vertex, then applies gravity, damping, and barycentrically distributed pinch force. Host readback occurs only after a run or validation segment.

CUDA graph capture is available with `--cuda-graph`; the final benchmark used 16 RK4 steps per graph chunk. Capture succeeded on the RTX 2060.

The fixture exporter in `scripts/calibrate_realtime_rk4.mjs` is the source of the exact topology and parameter data consumed by Warp.

## Domains benchmarked

| Character | Domain | Vertices | Triangles |
|---|---:|---:|---:|
| Female | micro | 128 | 206 |
| Female | screen | 1,000 | 1,855 |
| Female | full original island | 5,036 | 9,708 |
| Male | micro | 128 | 210 |
| Male | screen | 1,000 | 1,857 |
| Male | full original island | 41,920 | 82,807 |

## Final CPU/GPU benchmark

Duration was 0.001 seconds of simulated time. The benchmark used CUDA graphs and the tested controller values `Kp=0.1`, `Kd=0.01`. CPU and GPU ran identical fixture data.

| Model | Domain | CPU ms | GPU ms | Speedup | GPU max position error, source units | Flips | Collapses |
|---|---|---:|---:|---:|---:|---:|---:|
| Female | 128 | 64.1 | 16.4 | 3.9x | 5.175e-7 | 0 | 0 |
| Female | 1,000 | 1,386.0 | 35.0 | 39.6x | 9.478e-7 | 0 | 0 |
| Female | 5,036 | 8,630.6 | 253.0 | 34.1x | 1.706e-6 | 0 | 0 |
| Male | 128 | 47.0 | 10.4 | 4.5x | 9.003e-7 | 0 | 0 |
| Male | 1,000 | 576.3 | 18.7 | 30.8x | 2.079e-6 | 0 | 0 |
| Male | 41,920 | 53,611.2 | 375.7 | 142.7x | 3.083e-6 | 0 | 0 |

The full male island is therefore not yet real-time at this exact timestep and parameter set: 0.001 simulated seconds required 375.7 ms GPU wall time. This is a performance measurement, not a physical-validity rejection.

## Direct Node Float64 validation

The exact existing Node Float64 `simulate()` implementation generated the reference states in `gpu-cpu-references/`. At 0.0001 simulated seconds, the maximum GPU-versus-Node position errors were:

| Model | Domain | Gravity max error | Pinch-hold max error | Pinch-release max error |
|---|---|---:|---:|---:|
| Female | 5,036 | 6.678e-8 | 6.678e-8 | 1.909e-7 |
| Male | 41,920 | 1.381e-7 | 1.381e-7 | 3.980e-7 |

These are source-coordinate units. Normalized by face scale, the full-domain gravity errors are approximately 1.16e-6 for female and 4.54e-7 for male. The Float32 GPU trajectory is therefore numerically close to the existing Float64 reference over the tested interval.

The independent NumPy Float64 comparison at 0.001 seconds gave the same order of error and was used for the timing table.

## Geometry and energy

The final GPU benchmark produced zero orientation flips and zero collapsed triangles in gravity, pinch-hold, and release for all six domains. On the full original islands, the largest reported edge strains were:

- female: 0.04198% during release;
- male: 0.15673% during release.

Full-domain release mechanical energies were `8.544e-11 J` female and `1.982e-8 J` male in the benchmark model. These are diagnostics, not a claim that the long random-stress requirement has passed.

## Existing long-stress result preserved

The previously running full-male d10/Kp1/Kd1 20-sequence stress run completed and remains failed: 20 sequences executed, 7 genuine folds, 0 collapsed triangles. Its result is preserved at:

`verification/island-spring-pinch/rk4-controller-stress-parallel-full-n-20-w-20-damping10-stability16-male-full-20-parts.json`

This failure belongs to the physical/controller candidate, not to the GPU backend. The GPU migration does not relabel that candidate as successful.

## GPU full-island stress run

The same deterministic four-phase random-pinch protocol was also executed on both original full islands with the GPU backend, using the validated benchmark controller override `Kp=0.1`, `Kd=0.01`, seed `20261111`, 20 sequences per character, 1/60 s per held phase, and 0.05 s release. This is a separate candidate from the preserved failed CPU d10/Kp1/Kd1 run above.

| Character | Vertices | Sequences | GPU runtime | Folds | Collapses | Maximum edge strain | P95 edge strain | Minimum triangle-area ratio | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Female | 5,036 | 20 | 58.19 s | 0 | 0 | 0.3795% | 0.0399% | 0.96697 | PASS |
| Male | 41,920 | 20 | 238.76 s | 0 | 0 | 0.5028% | 0.0416% | 0.96563 | PASS |

The largest recorded pinch tracking errors were `0.0001789 m` female and `0.0010545 m` male. The stress result is a GPU execution/performance result; it does not retroactively validate the separately failed d10/Kp1/Kd1 physical candidate.

## Reproduction

```powershell
# Export exact CPU calibration fixtures
$env:VELA_CALIBRATION_MODELS='female,male'
$env:VELA_CALIBRATION_MASS_LOG='0'
$env:VELA_CALIBRATION_SURFACE_LOG='0'
$env:VELA_CALIBRATION_INNER_LOG='0'
$env:VELA_CALIBRATION_DAMPING_LOG='1'
$env:VELA_CALIBRATION_DT_LOG='-1'
$env:VELA_CALIBRATION_PINCH_KP_LOG='0'
$env:VELA_CALIBRATION_PINCH_KD_LOG='0'
$env:VELA_CALIBRATION_STABILITY_MULTIPLIER='16'
node scripts/calibrate_realtime_rk4.mjs --export-gpu-fixtures

# Export exact Node Float64 reference states
$env:VELA_GPU_REFERENCE_SECONDS='0.0001'
node scripts/calibrate_realtime_rk4.mjs --export-gpu-cpu-references

# Run the GPU/CPU benchmark on all requested sizes
python scripts/rk4_warp_gpu.py --seconds 0.001 --pinch-kp 0.1 --pinch-kd 0.01 --cuda-graph --output verification/island-spring-pinch/rk4-warp-gpu-final-benchmark.json

# Run the deterministic full-island GPU stress protocol
python scripts/rk4_warp_gpu.py --seconds 0.0001 --domains female:full,male:full --pinch-kp 0.1 --pinch-kd 0.01 --cuda-graph --stress-count 20 --stress-seed 20261111 --stress-output verification/island-spring-pinch/rk4-warp-gpu-stress-full-n20.json --output verification/island-spring-pinch/rk4-warp-gpu-stress-full-benchmark.json

# Start the local GPU browser bridge and HTTP preview
python scripts/warp_physics_server.py --manifest verification/island-spring-pinch/gpu-fixtures/manifest.json --port 8765
python serve.py 4174
# Open either original character in the existing browser UI:
# http://127.0.0.1:4174/island-spring-pinch.html?model=female&gpuServer=ws://127.0.0.1:8765
# http://127.0.0.1:4174/island-spring-pinch.html?model=male&gpuServer=ws://127.0.0.1:8765
```

## Status

Offline GPU acceleration is implemented and numerically validated against the existing Float64 reference for the tested gravity, pinch-hold, and release intervals. The long random-stress physical candidate remains failed, and the full male domain is not yet real-time at the measured configuration.

## Browser bridge validation

The browser still loads and renders the original GLBs. The local WebSocket bridge only owns the selected original island on the RTX device and returns evaluated positions at frame boundaries. It verifies the returned `globalVertexIds` against the browser's selected island before applying any positions; if no bridge is available, the existing CPU JavaScript path remains available.

The female GPU browser test loaded the original face, selected island 32 with 1,503 vertices and 2,857 triangles, held a barycentric pinch, and released it. The released state recorded a `1.3058e-5 m` tracking error, `5.1711e-4 N` peak force, and zero reported geometry defects. Evidence: `verification/island-spring-pinch/gpu-browser-pinched-released.png`.

The male browser test loaded the original GLB and selected its default source island 35 with 41,920 vertices and 82,807 triangles. The bridge alias maps the browser's `island-35` request to the matching full fixture, verified by a direct WebSocket bridge probe: `ready_domain=full`, `vertexCount=41920`, followed by a `0.001 s` GPU tick of 239 RK4 steps in `121.3 ms`. The neutral browser evidence is `verification/island-spring-pinch/gpu-browser-male-neutral.png`; that capture used the existing CPU fallback because the GPU handshake had not completed before the screenshot. The bridge now caches CUDA graphs for repeated frame advances and runs the GPU step off the browser event loop. A direct full-male `0.05 s` bridge advance completed 11,939 RK4 steps in `5,215.5 ms`, so the full male island remains decisively offline rather than real-time at this configuration. The female browser pinch is GPU-verified; the male browser endpoint and global-ID mapping are verified, but a complete male pointer replay is not claimed because the full-island physics cost exceeds the real-time frame budget.
