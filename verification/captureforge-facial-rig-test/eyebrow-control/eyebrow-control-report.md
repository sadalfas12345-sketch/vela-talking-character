# CaptureForge eyebrow-control diagnosis

Branch: `wip/tripo-face-repair`

Previous baseline: `8dacdd4`

No video coefficients were replayed. The test used the existing stored full landmark-105 target from Experiment 5.

## Root cause

The `brow.mid.R` bone is the CaptureForge control for landmark 105. Its three attached surface vertices carry very high `brow.mid.R` weights:

| Model | Triangle vertex weights |
|---|---|
| Female | 0.977508, 0.982643, 0.945857 |
| Male | 0.999842, 0.996472, 0.993143 |

The Armature modifier evaluated correctly on both models. The bone pivot is placed at the eyebrow landmark itself:

- Female bone length: `0.00440789`, eye width `0.05584185`
- Male bone length: `0.02424316`, eye width `0.29974317`

Therefore, rotating the bone around its existing pivot mostly rotates vertices around the landmark point. The attached landmark has almost no translational displacement even though surrounding weighted vertices move.

## Controlled isolation

At a 0.25-radian rotation of `brow.mid.R`:

| Measurement | Female | Male |
|---|---:|---:|
| Landmark 105 movement | `1.4463e-6` | `1.9073e-7` |
| Maximum vertex movement | `0.00032372` | `0.00178381` |
| Armature modifier | Evaluated | Evaluated |

At direct anatomical-up translation of 1% eye width:

| Measurement | Female | Male |
|---|---:|---:|
| Requested translation | `0.00055842` | `0.00299743` |
| Landmark 105 movement | `0.00054305` | `0.00298817` |
| Control response | `97.25%` | `99.69%` |

This isolates the defect to the rotation pivot/control mapping, not missing weights or modifier evaluation.

## Full landmark-105 target

The correction was tested by translating only `brow.mid.R` using landmark 105's stored full target vector. No other brow controls were moved.

| Measurement | Female | Male |
|---|---:|---:|
| Landmark 105 target error | `2.687%` | `0.304%` |
| Collapsed triangles | `0` | `0` |
| Minimum triangle area ratio | `0.5989` | `0.5969` |
| Maximum edge strain | `37.93%` | `40.56%` |
| P95 edge strain | approximately `2.55e-9` | approximately `1.34e-9` |
| Visual natural eyebrow raise | FAIL | FAIL |

The P95 strain is low because the damage is highly localized. The maximum strain and area ratios show that the direct translation concentrates deformation in a small local region. The textured close-ups do not show a convincing natural eyebrow raise, and the wire/clay evidence shows the localized deformation rather than a smooth forehead lift.

## Evidence

- Female [neutral](female/neutral.png), [full target](female/full-target.png)
- Male [neutral](male/neutral.png), [full target](male/full-target.png)
- Female [neutral wireframe](female/neutral-wireframe.png), [full target wireframe](female/full-target-wireframe.png)
- Male [neutral wireframe](male/neutral-wireframe.png), [full target wireframe](male/full-target-wireframe.png)
- Female [measurements](female/result.json)
- Male [measurements](male/result.json)

## Decision

ROOT CAUSE: **Identified** — the brow rotation pivot is located at the eyebrow landmark, so rotation creates surrounding motion but almost no landmark translation.

The direct anatomical translation correction proves that the weights can move landmark 105, but it produces excessive localized strain and fails the visual-quality requirement. Per the stop condition, no further correction or video playback was attempted.

FEMALE: **FAIL**

MALE: **FAIL**

EYEBROW DEFORMATION: **FAIL**

OVERALL STEP RESULT: **FAILED**
