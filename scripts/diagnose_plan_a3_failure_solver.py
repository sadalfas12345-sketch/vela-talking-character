"""Sweep only numerical linear-solve damping on the preserved A2 failure block."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components


def load_solver():
    path = Path(__file__).with_name("solve_plan_a2_hookean.py")
    spec = importlib.util.spec_from_file_location("plan_a3_solver", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--component", type=int, default=0)
    p.add_argument("--substep", type=int, default=1)
    p.add_argument("--substeps", type=int, default=20)
    p.add_argument("--iterations", type=int, default=150)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    s = load_solver()
    graph = np.load(a.graph)
    V = graph["V"].astype(float)
    F = graph["F"].astype(np.int64)
    T = graph["constraintTriangles"].astype(np.int64)
    B = graph["constraintBary"].astype(float)
    edges = np.vstack((graph["edgeSprings"], graph["virtualSprings"])).astype(np.int64)
    rest = np.concatenate((graph["edgeRestLengths"], graph["virtualRestLengths"])).astype(float)
    g = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]], graph["virtualSprings"]))
    conn = sparse.coo_matrix((np.ones(len(g)), (g[:, 0], g[:, 1])), shape=(len(V), len(V))).tocsr()
    count, labels = connected_components(conn, directed=False)
    verts = np.flatnonzero(labels == a.component)
    remap = -np.ones(len(V), dtype=np.int64)
    remap[verts] = np.arange(len(verts))
    eidx = np.all(np.isin(edges, verts), axis=1)
    local_edges = remap[edges[eidx]]
    local_rest = rest[eidx]
    ids = np.flatnonzero(labels[T[:, 0]] == a.component)
    local_tri = remap[T[ids]]
    targets = np.load(a.targets)["targets"].astype(float)
    desired = targets[0] + (a.substep / float(a.substeps)) * (targets[1] - targets[0])
    results = []
    for damping in [1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9, 1e-10]:
        _, report = s.solve_component(V[verts], local_edges, local_rest, local_tri, B[ids], desired[ids], a.iterations, 1e-9, 1e-8, 1e-8, linear_damping=damping)
        results.append({"linearDamping": damping, **{k: report[k] for k in ["status", "iterations", "finalConstraintResidual", "projectedGradientResidual", "maxStep", "springEnergy"]}})
    output = {"graph": str(a.graph), "component": a.component, "vertices": len(verts), "landmarks": len(ids), "substep": a.substep, "substeps": a.substeps, "results": results}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
