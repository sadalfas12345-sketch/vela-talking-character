# Goal 2: Existing Goal-1 Landmark Attachment Audit

This is a non-mutating visual and record audit. No landmark coordinates, mesh geometry, attachments, or trajectories were changed.

## Scope and evidence

The existing 30-point reference set contains 30 IDs. The eyebrow close-up was additionally inspected for 16 IDs. The remaining IDs are retained in the inventory but are not visually classified.

The 30-point classifications use the existing frontal and oblique evidence. They are not a new independent reference annotation. Eyebrow points are marked UNCERTAIN because the supplied textured close-ups do not independently resolve whether every point is on brow hair, brow skin, eyelid, or forehead skin.

## Counts

| Model | CORRECT | MISPLACED | UNCERTAIN | NOT_VISUALLY_AUDITED | Missing record |
|---|---:|---:|---:|---:|---:|
| female | 29 | 0 | 17 | 422 | 0 |
| male | 29 | 0 | 17 | 422 | 0 |

## Findings requiring attention

- **Female brow IDs 46, 53, 52, 65, 55, 70, 63, 105, 276, 283, 282, 295, 285, 336, 293, 334: UNCERTAIN.** The points are visible in the brow close-up, but the image does not establish a correct 3D anatomical attachment for each point. No point is declared MISPLACED from this evidence alone.
- **Male brow IDs 46, 53, 52, 65, 55, 70, 63, 105, 276, 283, 282, 295, 285, 336, 293, 334: UNCERTAIN** for the same reason. The male close-up appears visually more aligned, but that is not enough to certify every surface attachment.
- **Landmark 397: UNCERTAIN** in the existing selected set because the earlier Goal-1 evidence identifies the left jawline point as unresolved.
- **No confirmed MISPLACED attachment was established.** A successful raycast or barycentric reconstruction was not treated as anatomical proof.

## Exact attachment records

The machine-readable inventory preserves, for every model and ID, the hit mesh object, triangle index, triangle vertex indices, barycentric coordinates, mesh position, visibility flags, and audit status.

## Visual evidence

- `female-brow-questionable-attachments.png` and `male-brow-questionable-attachments.png` highlight the brow IDs in yellow because they remain uncertain.
- The original annotation plates remain unchanged in `verification/goal2-visual-landmark-annotation/`.
- Existing oblique attachment images were used as evidence and were not regenerated or altered.

## Decision

This audit does not authorize correction. The current evidence supports preserving the existing attachments and treating the brow set plus landmark 397 as unresolved pending a geometry-aware close-up review of the exact hit triangles.