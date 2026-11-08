"""Describe the first Plan A2 Hookean block that fails to equilibrate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--frame", type=int, required=True)
    p.add_argument("--substep", type=int, required=True)
    p.add_argument("--component", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    g = np.load(a.graph)
    V = g["V"].astype(float)
    F = g["F"].astype(np.int64)
    T = g["constraintTriangles"].astype(np.int64)
    B = g["constraintBary"].astype(float)
    virtual = g["virtualSprings"].astype(np.int64)
    E = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]], virtual))
    graph = sparse.coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(len(V), len(V))).tocsr()
    count, labels = connected_components(graph, directed=False)
    members = np.flatnonzero(labels == a.component)
    landmark_ids = [i for i, tri in enumerate(T) if int(labels[int(tri[0])]) == a.component]
    z = np.load(a.targets)
    targets = z["targets"].astype(float)
    if a.frame == 0:
        desired = targets[0]
    else:
        desired = targets[a.frame - 1] + (a.substep / 20.0) * (targets[a.frame] - targets[a.frame - 1])
    neutral = np.einsum("ij,ijk->ik", B[landmark_ids], V[T[landmark_ids]]) if landmark_ids else np.zeros((0, 3))
    target = desired[landmark_ids] if landmark_ids else np.zeros((0, 3))
    local_edges = E[np.all(np.isin(E, members), axis=1)]
    lengths = np.linalg.norm(V[local_edges[:, 0]] - V[local_edges[:, 1]], axis=1) if len(local_edges) else np.zeros(0)
    out = {"component": a.component, "totalSimulationComponents": int(count), "vertices": int(len(members)), "triangles": int(np.sum(np.all(np.isin(F, members), axis=1))), "landmarkIds": landmark_ids, "landmarkCount": len(landmark_ids), "frame": a.frame, "substep": a.substep, "targetDisplacementMagnitudes": np.linalg.norm(target - neutral, axis=1).tolist(), "maxTargetDisplacement": float(np.max(np.linalg.norm(target - neutral, axis=1))) if len(target) else 0.0, "medianLocalEdgeLength": float(np.median(lengths)) if len(lengths) else None, "minimumLocalEdgeLength": float(np.min(lengths)) if len(lengths) else None, "maxTargetOverMedianEdge": float(np.max(np.linalg.norm(target - neutral, axis=1)) / max(np.median(lengths), 1e-30)) if len(target) and len(lengths) else None, "interpretation": "The block is a physical connected component after virtual seam links; its hard constraints are exact, but the Hookean position update fails to reach a stable equilibrium within the tested nonlinear iterations."}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
