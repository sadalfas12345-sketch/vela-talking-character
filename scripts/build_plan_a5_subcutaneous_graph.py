"""Add Plan A5's abstract fixed subcutaneous anchor layer to an A2 graph.

The anchors are solver-only points and are not exported or rendered.  One
anchor is generated for every selected surface vertex at a local, normalized
inward depth.  Each surface vertex is linked to its own anchor and to up to
three adjacent anchors chosen from original mesh edges.  No source vertex or
triangle is changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--anchor-depth-fraction", type=float, default=0.25)
    p.add_argument("--neighbor-count", type=int, default=3)
    args = p.parse_args()
    g = np.load(args.graph)
    V = g["V"].astype(np.float64)
    F = g["F"].astype(np.int64)
    edges = g["edgeSprings"].astype(np.int64)
    virtual = g["virtualSprings"].astype(np.int64)
    all_edges = np.vstack((edges, virtual)) if len(virtual) else edges
    n = len(V)

    normals = np.zeros_like(V)
    face_n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    face_n /= np.maximum(np.linalg.norm(face_n, axis=1)[:, None], 1e-30)
    for tri, fn in zip(F, face_n):
        normals[tri] += fn
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-30)
    center = np.asarray(g["neutralLandmarks"], dtype=np.float64).mean(axis=0)
    radial = V - center
    signs = np.where(np.einsum("ij,ij->i", normals, radial) >= 0.0, 1.0, -1.0)
    outward = normals * signs[:, None]

    adjacency = [[] for _ in range(n)]
    for u, v in all_edges:
        u = int(u); v = int(v)
        if u == v:
            continue
        d = float(np.linalg.norm(V[u] - V[v]))
        adjacency[u].append((d, v))
        adjacency[v].append((d, u))
    local_scale = np.empty(n, dtype=np.float64)
    for i, neigh in enumerate(adjacency):
        ds = np.asarray([x[0] for x in neigh if x[0] > 1e-15], dtype=float)
        local_scale[i] = float(np.median(ds)) if len(ds) else 0.0
    positive = local_scale[local_scale > 0]
    fallback = float(np.median(positive)) if len(positive) else 1.0
    local_scale[local_scale <= 0] = fallback
    depth = float(args.anchor_depth_fraction) * local_scale
    anchors = V - outward * depth[:, None]

    surface = []
    anchor_index = []
    rest = []
    kind = []
    for i in range(n):
        surface.append(i); anchor_index.append(i); rest.append(float(np.linalg.norm(V[i] - anchors[i]))); kind.append("own")
        chosen = sorted(adjacency[i], key=lambda x: (x[0], x[1]))[: max(0, int(args.neighbor_count))]
        for d, j in chosen:
            surface.append(i); anchor_index.append(int(j)); rest.append(float(np.linalg.norm(V[i] - anchors[int(j)]))); kind.append("neighbor")

    out_npz = args.output.with_suffix(".npz")
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    for key in ("V", "F", "originalIndices", "constraintTriangles", "constraintBary", "neutralLandmarks"):
        if key not in g:
            raise ValueError(f"base graph missing {key}")
    np.savez_compressed(
        out_npz,
        V=V, F=F, originalIndices=g["originalIndices"],
        constraintTriangles=g["constraintTriangles"], constraintBary=g["constraintBary"],
        neutralLandmarks=g["neutralLandmarks"], edgeSprings=edges,
        edgeRestLengths=g["edgeRestLengths"], virtualSprings=virtual,
        virtualRestLengths=g["virtualRestLengths"],
        anchorPositions=anchors, anchorOutwardNormals=outward,
        anchorDepths=depth, supportSurfaceVertices=np.asarray(surface, dtype=np.int64),
        supportAnchorIds=np.asarray(anchor_index, dtype=np.int64),
        supportRestLengths=np.asarray(rest, dtype=np.float64),
        supportKind=np.asarray(kind),
    )
    report = {
        "sourceGraph": str(args.graph), "vertices": int(n), "triangles": int(len(F)),
        "originalSprings": int(len(edges)), "virtualSeamSprings": int(len(virtual)),
        "abstractAnchors": int(n), "supportSprings": int(len(surface)),
        "ownSupportSprings": int(sum(k == "own" for k in kind)),
        "neighborSupportSprings": int(sum(k == "neighbor" for k in kind)),
        "anchorDepthFractionOfLocalMedianEdge": float(args.anchor_depth_fraction),
        "neighborAnchorCount": int(args.neighbor_count),
        "anchorDepthMin": float(depth.min()), "anchorDepthMedian": float(np.median(depth)), "anchorDepthMax": float(depth.max()),
        "finiteAnchors": bool(np.isfinite(anchors).all()), "finiteRestLengths": bool(np.isfinite(rest).all()),
        "topologyChanged": False,
        "layerInterpretation": "abstract fixed solver control layer; not classified as anatomical subcutaneous tissue",
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
