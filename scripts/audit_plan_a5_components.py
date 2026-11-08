"""Audit retained facial components and their attached MediaPipe IDs for A5."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components


def audit(path: Path):
    z = np.load(path)
    V = z["V"].astype(float)
    F = z["F"].astype(np.int64)
    T = z["constraintTriangles"].astype(np.int64)
    edges = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]))
    conn = sparse.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(V), len(V))).tocsr()
    count, labels = connected_components(conn, directed=False)
    records = []
    for ci in range(count):
        verts = np.flatnonzero(labels == ci)
        lm = np.flatnonzero(labels[T[:, 0]] == ci).astype(int)
        records.append({
            "component": int(ci),
            "vertices": int(len(verts)),
            "triangles": int(np.sum(np.all(labels[F] == ci, axis=1))),
            "landmarkIds": lm.tolist(),
            "bboxMin": V[verts].min(axis=0).tolist(),
            "bboxMax": V[verts].max(axis=0).tolist(),
            "centroid": V[verts].mean(axis=0).tolist(),
        })
    out = {"source": str(path), "vertices": int(len(V)), "triangles": int(len(F)), "components": records}
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--female", type=Path, required=True)
    p.add_argument("--male", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    out = {"female": audit(a.female), "male": audit(a.male)}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: {"vertices": v["vertices"], "triangles": v["triangles"], "components": len(v["components"])} for k, v in out.items()}))


if __name__ == "__main__":
    main()
