"""Inspect conservative orientation reversals in an inverse-physics state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components


def angle(a, b):
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na <= 1e-15 or nb <= 1e-15:
        return None
    return float(np.degrees(np.arccos(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--positions", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--landmark", type=int, default=105)
    args = p.parse_args()

    g = np.load(args.graph)
    pos = np.load(args.positions)
    x0 = pos["originalPositions"].astype(float)
    x = pos["positions"].astype(float)
    F = g["F"].astype(np.int64)
    T = g["constraintTriangles"].astype(np.int64)
    W = g["constraintBary"].astype(float)
    source = g["originalIndices"].astype(np.int64)
    edges = np.vstack((g["edgeSprings"], g["virtualSprings"])).astype(np.int64)
    rest = np.concatenate((g["edgeRestLengths"], g["virtualRestLengths"])).astype(float)

    n = len(x0)
    adjacency = {}
    for fi, tri in enumerate(F):
        for a, b in ((int(tri[0]), int(tri[1])), (int(tri[1]), int(tri[2])), (int(tri[2]), int(tri[0]))):
            key = (min(a, b), max(a, b))
            adjacency.setdefault(key, []).append(fi)
    neighbors = [[] for _ in range(len(F))]
    for fs in adjacency.values():
        if len(fs) > 1:
            for fi in fs:
                neighbors[fi].extend(fj for fj in fs if fj != fi)

    v0 = x0[F[:, 1]] - x0[F[:, 0]]
    w0 = x0[F[:, 2]] - x0[F[:, 0]]
    v1 = x[F[:, 1]] - x[F[:, 0]]
    w1 = x[F[:, 2]] - x[F[:, 0]]
    n0 = np.cross(v0, w0)
    n1 = np.cross(v1, w1)
    area0 = np.linalg.norm(n0, axis=1)
    area1 = np.linalg.norm(n1, axis=1)
    reversed_ids = np.flatnonzero(np.sum(n0 * n1, axis=1) < 0)

    lm0 = np.sum(x0[T] * W[:, :, None], axis=1)
    lm1 = np.sum(x[T] * W[:, :, None], axis=1)
    landmark0 = lm0[args.landmark]
    landmark1 = lm1[args.landmark]

    conn = sparse.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(n, n)).tocsr()
    _, labels = connected_components(conn, directed=False)
    records = []
    for fi in reversed_ids:
        tri = F[fi]
        centroid0 = np.mean(x0[tri], axis=0)
        centroid1 = np.mean(x[tri], axis=0)
        neigh = sorted(set(neighbors[fi]))
        d0 = []
        d1 = []
        for fj in neigh:
            d0.append(angle(n0[fi], n0[fj]))
            d1.append(angle(n1[fi], n1[fj]))
        neighbor_dot = [float(np.dot(n1[fi], n1[fj]) / max(np.linalg.norm(n1[fi]) * np.linalg.norm(n1[fj]), 1e-30)) for fj in neigh]
        edge0 = [float(np.linalg.norm(x0[tri[(k + 1) % 3]] - x0[tri[k]])) for k in range(3)]
        edge1 = [float(np.linalg.norm(x[tri[(k + 1) % 3]] - x[tri[k]])) for k in range(3)]
        ratio = float(area1[fi] / max(area0[fi], 1e-30))
        coherent = bool(ratio > 0.2 and (not neighbor_dot or float(np.mean(neighbor_dot)) > 0.5))
        records.append({
            "localTriangleId": int(fi),
            "sourceVertexIds": source[tri].tolist(),
            "localVertexIds": tri.tolist(),
            "component": int(labels[int(tri[0])]),
            "neutralCentroid": centroid0.tolist(),
            "deformedCentroid": centroid1.tolist(),
            "distanceToLandmark105Neutral": float(np.linalg.norm(centroid0 - landmark0)),
            "distanceToLandmark105Deformed": float(np.linalg.norm(centroid1 - landmark1)),
            "neutralAreaDouble": float(area0[fi]),
            "deformedAreaDouble": float(area1[fi]),
            "areaRatio": ratio,
            "neutralEdgeLengths": edge0,
            "deformedEdgeLengths": edge1,
            "edgeRatios": [float(b / max(a, 1e-30)) for a, b in zip(edge0, edge1)],
            "edgeSharingNeighborIds": neigh,
            "neighborNeutralDihedralDegrees": d0,
            "neighborDeformedDihedralDegrees": d1,
            "deformedNeighborNormalDots": neighbor_dot,
            "rotationCandidate": coherent,
            "classification": "coherent_rotation_candidate" if coherent else "local_fold_candidate",
        })
    report = {
        "schema": "vela-inverse-reversal-audit-v1",
        "landmark": int(args.landmark),
        "triangleCount": int(len(F)),
        "reversalCount": int(len(reversed_ids)),
        "intersectionTest": "not performed; records distinguish orientation reversal from coherent neighbor rotation but do not prove self-intersection absence",
        "landmark105Neutral": landmark0.tolist(),
        "landmark105Deformed": landmark1.tolist(),
        "triangles": records,
        "summary": {"coherentRotationCandidates": int(sum(r["rotationCandidate"] for r in records)), "localFoldCandidates": int(sum(not r["rotationCandidate"] for r in records))},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reversalCount": len(records), **report["summary"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
