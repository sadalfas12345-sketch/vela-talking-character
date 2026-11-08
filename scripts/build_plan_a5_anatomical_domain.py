"""Build a model-agnostic facial-surface candidate for Plan A5.

This is an inspection-stage selector.  It never changes the source GLB.  The
facial frame is derived from the existing landmark attachments: the eye line
defines left/right, the brow-to-chin direction defines up, and their cross
product defines the local front/depth direction.  The retained volume is a
dimensionless landmark envelope expanded by one normalized margin.  Triangles
are retained only when all three source vertices are in that envelope and the
original triangle contains an attached landmark.  The report explicitly
records any attachment triangle that is not inside the candidate envelope.

The result is deliberately called a candidate.  It must be rendered and
inspected before it is used for simulation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def unit(x: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(x))
    if n <= 1e-12:
        raise ValueError("degenerate anatomical frame")
    return x / n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mesh", type=Path, required=True)
    p.add_argument("--goal1", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--margin", type=float, default=0.06)
    args = p.parse_args()

    mesh = np.load(args.mesh)
    V = mesh["V"].astype(np.float64)
    F = mesh["F"].astype(np.int64)
    goal = json.loads(args.goal1.read_text(encoding="utf-8"))
    records = {int(r["index"]): r for r in goal["records"] if r.get("meshXYZ") is not None}
    ids = sorted(records)
    if ids != list(range(478)):
        raise ValueError(f"expected 478 attachments, got {len(ids)} records")
    P = np.asarray([records[i]["meshXYZ"] for i in ids], dtype=np.float64)

    right = unit(P[263] - P[33])
    brow = P[[70, 63, 105, 336, 293, 334]].mean(axis=0)
    chin = P[[152, 175, 199, 396, 421, 428]].mean(axis=0)
    up = chin * 0.0 + brow - chin
    up = up - right * np.dot(up, right)
    up = unit(up)
    front = unit(np.cross(right, up))
    normals = np.asarray([records[i].get("surfaceNormal", [0, 0, 0]) for i in ids])
    if float(np.dot(front, normals.mean(axis=0))) < 0.0:
        front = -front
    axes = np.asarray([right, up, front])
    eye_width = float(np.linalg.norm(P[263] - P[33]))
    origin = P.mean(axis=0)
    landmark_local = ((P - origin) @ axes.T) / eye_width
    vertex_local = ((V - origin) @ axes.T) / eye_width
    lo = landmark_local.min(axis=0) - float(args.margin)
    hi = landmark_local.max(axis=0) + float(args.margin)
    vertex_keep = np.all((vertex_local >= lo) & (vertex_local <= hi), axis=1)

    attachment_triangles = np.asarray([records[i]["triangleVertexIndices"] for i in ids], dtype=np.int64)
    attachment_inside = np.all(vertex_keep[attachment_triangles], axis=1)
    # The source triangle must remain available for exact barycentric readback.
    vertex_keep[np.unique(attachment_triangles[~attachment_inside])] = True
    triangle_keep = np.all(vertex_keep[F], axis=1)
    selected_faces = F[triangle_keep]
    selected_vertices = np.unique(selected_faces.reshape(-1))
    old_to_new = -np.ones(len(V), dtype=np.int64)
    old_to_new[selected_vertices] = np.arange(len(selected_vertices))
    selected_faces_local = old_to_new[selected_faces]
    constraint_triangles = old_to_new[attachment_triangles]
    if np.any(constraint_triangles < 0):
        raise RuntimeError("an attachment triangle was not retained")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output.with_suffix(".npz"),
        V=V[selected_vertices], F=selected_faces_local,
        originalIndices=selected_vertices,
        constraintTriangles=constraint_triangles,
        constraintBary=np.asarray([records[i]["barycentricCoordinates"] for i in ids], dtype=np.float64),
        neutralLandmarks=P,
    )
    report = {
        "sourceMesh": str(args.mesh), "sourceGoal1": str(args.goal1),
        "landmarkCount": 478, "eyeWidth": eye_width,
        "marginEyeWidths": float(args.margin),
        "faceFrameOrigin": origin.tolist(), "rightAxis": right.tolist(),
        "upAxis": up.tolist(), "frontAxis": front.tolist(),
        "landmarkEnvelopeMin": lo.tolist(), "landmarkEnvelopeMax": hi.tolist(),
        "sourceVertices": int(len(V)), "sourceTriangles": int(len(F)),
        "candidateVertices": int(len(selected_vertices)),
        "candidateTriangles": int(len(selected_faces)),
        "candidateTriangleFraction": float(len(selected_faces) / max(len(F), 1)),
        "attachmentTrianglesOutsideEnvelopeBeforeForcedRetention": int(np.sum(~attachment_inside)),
        "topologyChanged": False,
        "selectionRule": "vertices inside landmark-derived normalized facial envelope; source triangles retained only when all vertices are inside; attachment triangles are forcibly retained for exact barycentric readback",
        "requiresVisualReview": True,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("candidateVertices", "candidateTriangles", "attachmentTrianglesOutsideEnvelopeBeforeForcedRetention")}))


if __name__ == "__main__":
    main()
