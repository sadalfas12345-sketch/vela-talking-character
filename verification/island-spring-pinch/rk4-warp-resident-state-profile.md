# Warp resident-state profile

Generated 2026-11-13.

## Change

The GPU stress loop now keeps each sequence resident in `WarpSimulation` across the four held-pinch phases and release. It uses `advance()` so the existing graph cache can reuse graphs across phase target updates. The Hookean force kernels, RK4 equations, masses, anchors, and controller values are unchanged.

## Male full-island comparison

Both runs used the same fixture, seed, one sequence, 16.7 ms hold, 20 ms release, graph chunk 16, and calibrated controller.

| Path | Runtime | Result |
|---|---:|---|
| Previous phase-reset path | 53.138 s | PASS |
| Resident-state path | 52.870 s | PASS |

Both runs had zero folds and zero collapsed triangles.

The measured improvement is approximately 0.5%, so host state transfers are not the dominant bottleneck. The remaining cost is per-step RK4 kernel execution and graph scheduling on the 41,920-vertex domain.

The resident-path output is `rk4-warp-gpu-resident-male-stress.json`.

