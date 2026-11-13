# RK4 parameter tradeoff diagnostic

Generated 2026-11-13.

The purpose of this diagnostic was to test whether the full-domain substep bottleneck could be reduced by the explicitly permitted mass, stiffness, and damping parameters without changing the Hookean model.

## Low-stiffness candidate

Candidate logs:

```text
mass=0.3, surface=-1, inner=-2, damping=0, dt=-1, Kp=-2.5, Kd=-1
```

At the default 20 ms gravity window it remained unsettled, although it was finite and had no flips in that short window. Its estimated stable timesteps were:

- Female: 3.996 µs, 4,172 substeps per frame.
- Male: 6.073 µs, 2,745 substeps per frame.

The longer 200 ms gravity audit reached settling on both micro domains, but the female developed three orientation flips and one genuine fold on face 199. The male remained valid. This candidate is rejected as a shared physical configuration.

Evidence: `rk4-gravity-audit.json`.

## High-damping variant

Candidate logs:

```text
mass=0.3, surface=-1, inner=-2, damping=2, dt=-1, Kp=-2.5, Kd=-1
```

It passed the short micro physical and three-sequence stress checks, but damping limited the stable timestep to 4.325 µs on the male, worse than the low-damping candidate and still too slow for the full real-time target.

## Conclusion

The tested stiffness reduction trades timestep size for female gravitational folding, while the damping required to settle that deformation removes the timestep benefit. No parameter change in this controlled test is accepted as a replacement for the validated baseline. The remaining performance bottleneck is execution cost at the physically valid timestep, not an untested claim that lower stiffness is safe.

