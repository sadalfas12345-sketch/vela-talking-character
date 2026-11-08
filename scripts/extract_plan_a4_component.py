"""Extract one connected spring-graph component for a bounded A4 regression."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--component", type=int, required=True)
    p.add_argument("--frame", type=int, default=2)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    src = np.load(a.graph)
    V = src["V"].astype(float)
    F = src["F"].astype(np.int64)
    T = src["constraintTriangles"].astype(np.int64)
    B = src["constraintBary"].astype(float)
    edges = np.vstack((src["edgeSprings"], src["virtualSprings"])).astype(np.int64)
    rest = np.concatenate((src["edgeRestLengths"], src["virtualRestLengths"])).astype(float)
    graph_edges = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]], src["virtualSprings"])).T
    graph_edges = graph_edges.T if graph_edges.shape[0] == 2 else graph_edges
    conn = sparse.coo_matrix((np.ones(len(graph_edges)), (graph_edges[:, 0], graph_edges[:, 1])), shape=(len(V), len(V))).tocsr()
    count, labels = connected_components(conn, directed=False)
    if a.component < 0 or a.component >= count:
        raise SystemExit(f"component {a.component} out of range 0..{count - 1}")
    verts = np.flatnonzero(labels == a.component)
    remap = -np.ones(len(V), dtype=np.int64)
    remap[verts] = np.arange(len(verts))
    tri_mask = np.all(labels[F] == a.component, axis=1)
    lm_mask = np.all(labels[T] == a.component, axis=1)
    edge_mask = np.all(np.isin(edges, verts), axis=1)
    targets = np.load(a.targets)["targets"].astype(float)[a.frame]
    a.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        a.output,
        V=V[verts],
        F=remap[F[tri_mask]],
        originalIndices=src["originalIndices"][verts],
        constraintTriangles=remap[T[lm_mask]],
        constraintBary=B[lm_mask],
        edgeSprings=remap[edges[edge_mask]],
        edgeRestLengths=rest[edge_mask],
        virtualSprings=np.empty((0, 2), dtype=np.int64),
        virtualRestLengths=np.empty(0, dtype=float),
        componentLabels=np.zeros(len(verts), dtype=np.int32),
        neutralLandmarks=src["neutralLandmarks"][lm_mask],
        targetLandmarks=targets[lm_mask],
    )
    print({"sourceComponents": int(count), "component": a.component, "vertices": int(len(verts)), "triangles": int(np.sum(tri_mask)), "landmarks": int(np.sum(lm_mask)), "edges": int(np.sum(edge_mask))})


if __name__ == "__main__":
    main()
