"""Report component sizes and hard landmark-constraint counts for Plan A2."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    d = np.load(a.graph)
    V = d["V"]
    F = d["F"].astype(np.int64)
    T = d["constraintTriangles"].astype(np.int64)
    edges = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]], d["virtualSprings"].astype(np.int64)))
    g = sparse.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(V), len(V))).tocsr()
    n, lab = connected_components(g, directed=False)
    counts = Counter(int(lab[int(t[0])]) for t in T)
    sizes = Counter(map(int, lab))
    rows = [{"component": c, "vertices": sizes[c], "landmarks": counts.get(c, 0)} for c in range(n)]
    rows.sort(key=lambda x: (x["vertices"], x["landmarks"]), reverse=True)
    out = {"vertices": len(V), "triangles": len(F), "components": n, "componentsWithLandmarks": sum(1 for x in rows if x["landmarks"]), "largest": rows[:20], "singletonLandmarkComponents": sum(1 for x in rows if x["vertices"] <= 3 and x["landmarks"]), "oneLandmarkComponents": sum(1 for x in rows if x["landmarks"] == 1)}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
