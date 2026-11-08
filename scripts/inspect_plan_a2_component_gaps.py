"""Measure candidate boundary gaps for Plan A2's retained components."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree
from scipy.sparse.csgraph import connected_components


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--patch", type=Path, required=True)
    p.add_argument("--goal1", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--gap-fractions", type=float, nargs="+", default=[0.03, 0.05, 0.10, 0.15, 0.20])
    a = p.parse_args()
    d = np.load(a.patch)
    V = d["V"].astype(float)
    F = d["F"].astype(np.int64)
    T = d["constraintTriangles"].astype(np.int64)
    goal = json.loads(a.goal1.read_text(encoding="utf-8"))
    rec = {int(x["index"]): x for x in goal["records"] if x.get("meshXYZ") is not None}
    eye = float(np.linalg.norm(np.asarray(rec[263]["meshXYZ"]) - np.asarray(rec[33]["meshXYZ"])))
    edges = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]))
    graph = sparse.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(V), len(V))).tocsr()
    count, labels = connected_components(graph, directed=False)
    attached = np.unique(labels[T[:, 0]])
    keep = np.isin(labels, attached)
    labels = labels[keep]
    old = np.flatnonzero(keep)
    remap = -np.ones(len(V), dtype=np.int64)
    remap[old] = np.arange(len(old))
    F = remap[F[np.all(keep[F], axis=1)]]
    T = remap[T]
    V = V[old]
    # Rebuild the graph after remapping; slicing the pre-remap graph would
    # compare unrelated vertex IDs and corrupt the component counts.
    edges = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]))
    graph = sparse.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(V), len(V))).tocsr()
    edges = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]))
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    counts = Counter(map(tuple, edges.tolist()))
    boundary = np.asarray(sorted({v for e, n in counts.items() if n == 1 for v in e}), dtype=np.int64)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1)[:, None], 1e-30)
    vn = np.zeros_like(V)
    for tri, n in zip(F, fn):
        vn[tri] += n
    vn /= np.maximum(np.linalg.norm(vn, axis=1)[:, None], 1e-30)
    skin = set()
    eye_only = {33, 133, 263, 362} | set(range(468, 478))
    for idx, tri in enumerate(T):
        skin.add(int(labels[int(tri[0])]))
    ids_by_comp = {int(ci): [] for ci in np.unique(labels)}
    for lid, tri in enumerate(T):
        ids_by_comp[int(labels[int(tri[0])])].append(lid)
    class_by = {ci: ("eye_or_iris" if ids and set(ids).issubset(eye_only) else "facial_skin_candidate") for ci, ids in ids_by_comp.items()}
    tree = cKDTree(V[boundary])
    candidates = {}
    max_r = max(a.gap_fractions) * eye
    for local_v in boundary:
        ci = int(labels[local_v])
        if class_by[ci] != "facial_skin_candidate":
            continue
        for bi in tree.query_ball_point(V[local_v], max_r):
            other = int(boundary[bi])
            cj = int(labels[other])
            if ci == cj or class_by[cj] != "facial_skin_candidate":
                continue
            gap = float(np.linalg.norm(V[local_v] - V[other]))
            nd = float(np.dot(vn[local_v], vn[other]))
            if nd < 0.65:
                continue
            key = tuple(sorted((ci, cj)))
            row = (gap, nd, int(local_v), other)
            if key not in candidates or row < candidates[key]:
                candidates[key] = row
    rows = []
    gaps = np.asarray([x[0] / eye for x in candidates.values()], dtype=float)
    for frac in a.gap_fractions:
        n = sum(x[0] <= frac * eye for x in candidates.values())
        vv = np.asarray([[x[2], x[3]] for x in candidates.values() if x[0] <= frac * eye], dtype=np.int64)
        sg = sparse.coo_matrix((np.ones(len(vv)), (vv[:, 0], vv[:, 1])), shape=(len(V), len(V))).tocsr() if len(vv) else sparse.csr_matrix(graph.shape)
        total, _ = connected_components((graph + sg).astype(bool), directed=False)
        rows.append({"gapFraction": frac, "virtualPairCount": int(n), "simulationComponents": int(total)})
    out = {"vertices": int(len(V)), "retainedComponents": int(len(np.unique(labels))), "eyeWidth": eye, "candidatePairCountAtMaxRadius": int(len(candidates)), "candidateGapMin": float(gaps.min()) if len(gaps) else None, "candidateGapMedian": float(np.median(gaps)) if len(gaps) else None, "candidateGapP95": float(np.percentile(gaps, 95)) if len(gaps) else None, "candidateGapMax": float(gaps.max()) if len(gaps) else None, "thresholds": rows}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
