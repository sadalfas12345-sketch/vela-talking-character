# Open-source facial-rigging evaluation

Date: 2026-11-05

## Decision

Do not import an external implementation or checkpoint into the Vela runtime. The strongest
usable path for this repository remains offline deformation transfer using the already-integrated
Avaturn donor and the preserved Tripo assets, followed by a topology-aware local transition.

The external projects below are useful as research references, but none is a clean production
drop-in for this checkout without changing the licensing, hardware, or topology assumptions.

| Project | Verified capability | License / distribution | Fit for this task |
|---|---|---|---|
| Mesh Expression Retargeter | Blender add-on; manual landmark pairing or overlapping-surface nearest-surface mapping; writes native shape keys. It explicitly documents separate-inner-lip limitations. | GPL-3.0. | Not selected for shipped integration. It can inform correspondence UX, but its license is incompatible with an unreviewed production dependency and it does not solve the missing mouth topology. |
| TopoRig | Predicts facial blendshape deformations for neutral GLB, FBX, or OBJ meshes. Its demo includes optional mouth postprocessing that separates joined lips and fits teeth and tongue, plus eye postprocessing. | TopoRig Academic Use License 1.0; code and checkpoints are noncommercial academic research only. | Strongest research candidate for an isolated experiment, not production. It requires a separate Python 3.11 and PyTorch 2.7 environment, Blender, downloaded checkpoints, and external data. Do not add its checkpoints to this repository or claim commercial clearance. |
| NFR_pytorch | Neural retargeting across different topology; releases code and pretrained data path. | MIT code. Checkpoints and datasets need separate provenance review. | Not selected. Official setup targets Ubuntu 20.04 and RTX 4090, Windows is not supported, and custom targets must have cut mouth and eye/nose regions without internal sockets. That conflicts with the current closed Tripo shell and this Windows RTX 2060 workstation. |
| OmniFaceRig | Research materials include inner-mouth-aware rigged assets, solved templates, oral-related rig exports, keypoints, and 1,345 dataset assets. | FAIR Noncommercial Research License v1. | Not selected for production. The public repository is a research-materials/dataset release, not a verified runnable inference pipeline for this GLB, and the license restricts use to noncommercial research. |

## Selection rationale

The existing Avaturn route is the only evaluated route already producing live TalkingHead and
HeadTTS morph activity in this checkout. The remaining defect is not a lack of a retargeting
algorithm; it is the visible transition between the fitted facial surface and the retained Tripo
head shell. The next implementation must therefore repair that boundary without replacing Tripo
hair, body, clothing, or original GLBs.

The current face-fit prototype is not accepted. Its rendered neutral and jaw-open frames show
jagged forehead and temple boundaries, dark cavities, and a broken lower jaw/neck transition.

## Sources

- Mesh Expression Retargeter: https://github.com/Vidyut/mesh-expression-retargeter
- TopoRig: https://github.com/TaatiTeam/TopoRig
- NFR_pytorch: https://github.com/dafei-qin/NFR_pytorch
- OmniFaceRig: https://github.com/facebookresearch/omnifacerig
