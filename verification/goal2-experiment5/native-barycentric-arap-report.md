# Experiment 5: exact native barycentric constraints

The native bridge uses the official libigl ARAP local/global machinery and
`min_quad_with_fixed` sparse equality solver. The two landmark equations are
assembled directly over the original patch vertices:

```text
w70,A * V_A + w70,B * V_B + w70,C * V_C = target70
w105,A * V_A + w105,B * V_B + w105,C * V_C = target105
```

No temporary handle vertex is used in this result, and original vertex order,
topology, and Goal-1 attachments are unchanged.

## Exact two-landmark result

| Model | ID 70 error | ID 105 error | Constraint residual max | New inversions | Collapses | Max edge strain | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| Female | <3e-11% | <3e-11% | 2.25e-16 | 2 | 0 | 39.309% | FAIL |
| Male | <3e-11% | <3e-11% | 2.10e-16 | 44 | 0 | 71.289% | FAIL |

The numerical constraint requirement passes, but geometry integrity fails.

## Cause isolation

Using the same 128-hop patches and exact native barycentric equations:

| Controls | Female inversions | Male inversions | Female max strain | Male max strain |
|---|---:|---:|---:|---:|
| 70 only | 0 | 3 | 30.673% | 37.861% |
| 105 only | 2 | 41 | 39.309% | 71.289% |
| 70 + 105 | 2 | 44 | 39.309% | 71.289% |

Landmark 105 alone reproduces essentially the full two-control damage. The
combined constraint is not the primary cause. Landmark 70 alone remains the
female Experiment-4-compatible case; 105 is the first failing target on both
models.

Expanding the connected patch from 128 to 256 hops produced:

| Model | Inversions at 256 hops | ID 70 error | ID 105 error | Max strain |
|---|---:|---:|---:|---:|
| Female | 2 | <3e-11% | <3e-11% | 39.309% |
| Male | 45 | <3e-11% | <3e-11% | 71.230% |

Thus the demonstrated failure is not repaired by simply enlarging the outer
support. The prescribed landmark-105 target is geometrically incompatible with
the current original surface and stationary boundary under this ARAP solve,
or requires a targeted local fold-preserving correction that has not yet been
validated. No target attenuation, triangle deletion, or winding change was
used.

Machine-readable outputs:

- `native-barycentric-arap/results-2-native-barycentric-arap.json`
- `native-barycentric-arap-single-70/results-1-native-barycentric-arap.json`
- `native-barycentric-arap-single-105/results-1-native-barycentric-arap.json`
- `native-barycentric-arap-256/results-2-native-barycentric-arap.json`

No four- or six-landmark tests were run.

## Targeted correction attempt

The existing model-agnostic shared-edge correction was applied to the exact
ARAP result, followed by a fresh exact constrained ARAP solve after every
correction round. This preserves the two barycentric equations but does not
leave a post-hoc mesh.

| Model | Baseline inversions | Corrected inversions | Landmark residual after correction | Result |
|---|---:|---:|---:|---|
| Female | 2 | 7 | <4e-13 relative | FAIL |
| Male | 44 | 95 | <5e-13 relative | FAIL |

The correction therefore does not resolve the demonstrated landmark-105
geometric incompatibility. No further parameter or support tuning was run.
