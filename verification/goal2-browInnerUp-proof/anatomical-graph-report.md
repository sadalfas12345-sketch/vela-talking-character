# Goal 2 anatomy-aware graph checkpoint

The restored `eab30f95` QP solver and Goal 1 artifacts were left unchanged.

The imported characters are single dense meshes with one material slot, so material identity cannot classify skin versus hair. The new preprocessing stage therefore uses only model-derived evidence: coincident world position, transformed vertex-normal agreement, and agreement with a Goal 1 landmark-derived facial region inside a 2.25 interocular-distance envelope.

| Model | Candidate coincident pairs | Accepted skin-surface ties | Rejected | Rejection reason |
|---|---:|---:|---:|---|
| Female | 2,643 | 2,637 | 6 | normal mismatch |
| Male | 22,460 | 22,456 | 4 | normal mismatch |

Accepted ties are stored in the graph NPZ files. No welding or GLB topology edits were performed. The accepted graph has not yet been inserted into the production solver because the earlier unconstrained duplicate-tie experiment introduced 22 female inversions at full weight. That failure is preserved and the stable solver remains active.

This checkpoint is therefore not a Goal 2 pass. The remaining implementation requirement is a coupled solve that uses the accepted skin ties, a smooth boundary halo, and triangle-quality constraints without imposing donor constraints that conflict with the seam graph.
