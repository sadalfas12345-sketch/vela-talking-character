# VELA Plan A5 — revised Stage B functional gate

Status: **Stage B functional gate FAILED; dependent full animation stages not started**

Branch: `wip/tripo-face-repair`

The Stage B rule was revised as requested. Anatomical purity is not a gate.
Hair, beard, neck, disconnected components, and the visible placement of the
abstract layer are allowed. The original GLBs and all source vertices remain
unchanged.

## Revised acceptance gates

Stage B now checks only:

1. Existing landmark correspondence is present for IDs `0–477`.
2. Barycentric triangles and weights are finite and reconstruct neutral points.
3. Abstract fixed-anchor positions and support rest lengths are finite.
4. Neutral solve preserves the original coordinates and topology.
5. Expression probes produce finite geometry and a stable numerical state.
6. Visual artifacts are reported separately from the objective numerical gates.

Hair, beard, neck, and component count are descriptive observations only.

## Inputs and abstract layer

| Character | Solver graph | Vertices | Triangles | Original springs | Virtual seams | Abstract anchors |
|---|---|---:|---:|---:|---:|---:|
| Female | `female-subcutaneous-r050.npz` | 41,747 | 79,627 | 121,358 | 24 | 41,747 |
| Male | `male-subcutaneous-r050.npz` | 208,351 | 401,474 | 609,759 | 146 | 208,351 |

The support layer uses the same deterministic rule on both models:

- one non-rendered fixed anchor per selected vertex;
- inward depth `0.25 × local median incident edge length`;
- one own-anchor spring plus three adjacent-anchor springs per surface vertex;
- no source topology, vertex IDs, or GLB data are changed.

| Character | Support springs | Anchor depth min / median / max | Finite anchors | Finite rest lengths |
|---|---:|---:|---|---|
| Female | 166,796 | `5.09e-05 / 1.76e-04 / 8.70e-04` | YES | YES |
| Male | 832,561 | `9.93e-05 / 4.38e-04 / 1.51e-03` | YES | YES |

This layer is explicitly abstract. It is not claimed to be anatomically
subcutaneous tissue.

## Correspondence and neutral preservation

Both characters retain `478/478` landmark attachments. All triangle indices,
weights, and neutral target arrays are finite. Weight sums differ from one by
at most `2.22e-16`.

The male data contains one row with a small negative barycentric weight
`-1.42485e-04`; it is finite and preserved as supplied rather than silently
clamped. This is recorded as an attachment-quality warning, not relabeled as
an anatomical-domain failure.

Neutral supported solves:

| Character | Max neutral vertex displacement | Max landmark error | Collapsed triangles | Normal reversals |
|---|---:|---:|---:|---:|
| Female | `2.78e-16` | `5.72e-17` | 0 | 0 |
| Male | `6.36e-17` | `5.59e-17` | 0 | 0 |

Neutral geometry and connectivity were preserved to floating-point precision.

## Expression and head-motion probes

The source table is head-stabilized. It does not contain an independent rigid
head-motion target. Therefore the head test is reported separately as a
synthetic rigid transport check, not misrepresented as measured facial motion.

The expression frame labels below are signal-based observations from the
existing table. The performance is mixed, so `mouth/smile-like` does not claim
an isolated psychological smile.

| Probe | Source-frame basis |
|---|---|
| Neutral | frame 0 |
| Blink/eyelid peak | frame 45, maximum selected eyelid signal |
| Mouth/smile-like peak 1 | frame 97, maximum selected mouth signal |
| Mouth/smile-like peak 2 | frame 99, adjacent high mouth/brow signal |
| Head motion | synthetic 5° in-plane rotation + 0.03 IPD translation |

The same supported solver was run independently on both characters. The solver
uses the existing sparse projected Hookean update and exact barycentric
constraints. The probe output is intentionally bounded; a `max_iterations`
status is reported as a numerical failure, not silently accepted as equilibrium.

| Character / frame | Max target readback error | Max edge strain | P95 abs edge strain | Area collapses | Normal reversals | Solver status |
|---|---:|---:|---:|---:|---:|---|
| Female 45 | `4.585e-03` | `15.753` | `0.280` | 0 | 1,819 | FAILED: max iterations |
| Female 97 | `3.318e-03` | `21.190` | `0.547` | 0 | 2,228 | FAILED: max iterations |
| Female 99 | `3.440e-03` | `21.066` | `0.563` | 0 | 2,272 | FAILED: max iterations |
| Male 45 | `2.109e-02` | `37.023` | `0.107` | 0 | 4,549 | FAILED: max iterations |
| Male 97 | `1.361e-02` | `86.418` | `0.136` | 0 | 3,767 | FAILED: max iterations |
| Male 99 | `1.501e-02` | `85.232` | `0.140` | 0 | 3,853 | FAILED: max iterations |

The component-local hard residuals were approximately machine precision for
the components actually solved, but the full readback errors remain nonzero
because the solver stopped after the first component at the bounded iteration
limit. Exact landmark placement alone is therefore not treated as success.

Head transport passed on both characters:

| Character | Max barycentric transport error |
|---|---:|
| Female | `1.12e-16` |
| Male | `1.15e-16` |

This verifies the character-relative correspondence under rigid transport. It
does not prove that the current elastic solver can animate head motion.

## Visual review, separate from objective gates

The neutral renders preserve the original faces. The supported expression
renders show severe visible deformation artifacts, including large spikes and
surface foldovers in hair and facial regions. Allowing hair and beard to move
does not make these artifacts acceptable.

- [Female neutral](female-stageb-frame45-neutral.png)
- [Female supported probe](female-stageb-frame45-supported.png)
- [Male neutral](male-stageb-frame45-neutral.png)
- [Male supported probe](male-stageb-frame45-supported.png)

The earlier red-domain images remain diagnostic only and are not failures by
themselves:

- [Female domain](female-r050-domain.png)
- [Male domain](male-r050-domain.png)

## Stage B decision

| Gate | Result | Evidence |
|---|---|---|
| Landmark correspondence | PASS | 478/478 finite attachments on both |
| Anchor weights/positions finite | PASS with warning | finite; one male slightly negative barycentric weight preserved |
| Neutral preservation | PASS | max displacement below `3e-16` |
| Rigid head transport | PASS | max error below `1.2e-16` on both |
| Stable expression deformation | FAIL | all tested non-neutral probes stopped at max iterations |
| Visual artifact review | FAIL | spikes/foldovers visible in supported renders |

Because the functional deformation gate fails, the later A5 stages were not
started:

- Stage C short contiguous sequence: **NOT RUN**
- Stage D frame 30: **NOT RUN**
- Stage E complete 121-frame animation: **NOT RUN**

This revision removes anatomical purity and component count as blockers, but it
does not waive numerical stability or visible geometry failures.

## Reproduction

```powershell
cd C:\Users\USER\talking-character-demo
python scripts/build_plan_a5_subcutaneous_graph.py --graph verification/plan-a5-subcutaneous-run/female-spring-graph-r050.npz --output verification/plan-a5-subcutaneous-run/female-subcutaneous-r050.json
python scripts/build_plan_a5_subcutaneous_graph.py --graph verification/plan-a5-subcutaneous-run/male-spring-graph-r050.npz --output verification/plan-a5-subcutaneous-run/male-subcutaneous-r050.json
python scripts/solve_plan_a5_subcutaneous.py --graph verification/plan-a5-subcutaneous-run/female-subcutaneous-r050.npz --targets verification/plan-a5-subcutaneous-run/female-targets-r050.npz --output verification/plan-a5-subcutaneous-run/female-stageb-frame45-supported.json --frame 45 --support-ratio 0.1 --max-iterations 20 --inner-iterations 60
python scripts/solve_plan_a5_subcutaneous.py --graph verification/plan-a5-subcutaneous-run/male-subcutaneous-r050.npz --targets verification/plan-a5-subcutaneous-run/male-targets-r050.npz --output verification/plan-a5-subcutaneous-run/male-stageb-frame45-supported.json --frame 45 --support-ratio 0.1 --max-iterations 2 --inner-iterations 20
python scripts/test_plan_a5_head_motion_transport.py --graph verification/plan-a5-subcutaneous-run/female-subcutaneous-r050.npz --output verification/plan-a5-subcutaneous-run/female-head-motion-transport.json
```

The equivalent male head-transport command substitutes the male graph/output.

OVERALL STEP RESULT: **FAILED**

Failure mechanism: correspondence and abstract-anchor construction are
functional, but the first non-neutral supported Hookean probes do not reach a
stable converged deformation and produce severe visible artifacts. No full
animation claim is made.
