# Goal 2 anatomical physics preprocessing

This checkpoint preserves the original render meshes and the restored experimental QP baseline. It adds a separate face-only coarse physics surface and a cached render embedding.

| Model | Face render vertices | Physics nodes | Physics triangles | Stretch springs | Bend edges | Frontalis fibers | Neutral error P95 | Face embedding coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Female | 135,183 | 7,229 | 9,617 | 16,766 | 12,085 | 2,006 | 0 | 99.9867% |
| Male | 481,671 | 9,416 | 9,506 | 18,168 | 10,350 | 2,695 | 0 | 99.7502% |

The physics surface is extracted from a Goal 1 landmark-derived face envelope, decimated independently of the render topology, and connected with stretch edges and shared-triangle bending edges. Render vertices retain their original IDs and are embedded with a physics triangle, barycentric weights, and a neutral offset. At zero activation, the cached embedding reconstructs the original face vertices within floating-point precision.

The current region classifier is geometry-derived and labels brow, eyelid, eye, nose, mouth, and jaw physics nodes. It is not yet a complete biological skin-versus-hair classifier. No muscle equilibrium solve has been accepted yet, and no expression GLB was generated from this new physics path.

Status: preprocessing PASS, physics-to-render neutral validation PASS, Goal 2 expression validation UNVERIFIED.
