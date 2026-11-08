"""Build Plan A2's original-edge and justified virtual-seam spring graph."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy import sparse
from scipy.sparse.csgraph import connected_components


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--patch", type=Path, required=True)
    p.add_argument("--goal1", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--boundary-k", type=int, default=8)
    a = p.parse_args()
    patch = np.load(a.patch)
    V_all = patch["V"].astype(np.float64)
    F_all = patch["F"].astype(np.int64)
    T_all = patch["constraintTriangles"].astype(np.int64)
    B = patch["constraintBary"].astype(np.float64)
    goal = json.loads(a.goal1.read_text(encoding="utf-8"))
    records = {int(r["index"]): r for r in goal["records"] if r.get("meshXYZ") is not None}

    # Original topology components. Components without any Goal 1 attachment
    # are outside the minimal facial simulation domain and are not copied.
    mesh_edges = np.vstack((F_all[:, [0, 1]], F_all[:, [1, 2]], F_all[:, [2, 0]]))
    graph = sparse.coo_matrix((np.ones(len(mesh_edges)), (mesh_edges[:, 0], mesh_edges[:, 1])), shape=(len(V_all), len(V_all))).tocsr()
    component_count, labels = connected_components(graph, directed=False)
    # Keep every topology component touched by any vertex of a stored
    # barycentric attachment.  Some Goal-1 raycasts came from polygon triples
    # that are not emitted as one loop-triangle by Blender, so using only the
    # first attachment vertex can silently turn the other two into -1.
    attached_components = np.unique(labels[T_all.reshape(-1)])
    keep = np.isin(labels, attached_components)
    old_to_new = -np.ones(len(V_all), dtype=np.int64)
    kept_old = np.flatnonzero(keep)
    old_to_new[kept_old] = np.arange(len(kept_old))
    F = old_to_new[F_all[np.all(keep[F_all], axis=1)]]
    T = old_to_new[T_all]
    V = V_all[kept_old]
    component_labels = labels[kept_old]

    # Original edge springs, deduplicated and with neutral rest lengths.
    edges = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]))
    edges = np.sort(edges, axis=1)
    edges = np.unique(edges, axis=0)
    rest = np.linalg.norm(V[edges[:, 0]] - V[edges[:, 1]], axis=1)

    # Boundary vertex normals are used only to reject cross-layer connections.
    face_normals = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    norm = np.linalg.norm(face_normals, axis=1)
    face_normals /= np.maximum(norm[:, None], 1e-30)
    edge_counts = Counter(tuple(x) for x in edges.tolist())
    boundary = sorted({v for edge, count in edge_counts.items() if count == 1 for v in edge})
    vertex_normal = np.zeros_like(V)
    for tri, n in zip(F, face_normals):
        vertex_normal[tri] += n
    vertex_normal /= np.maximum(np.linalg.norm(vertex_normal, axis=1)[:, None], 1e-30)

    landmark_ids_by_component = defaultdict(list)
    for i, tri in enumerate(T):
        landmark_ids_by_component[int(component_labels[int(tri[0])])].append(i)

    eye_only_ids = {33, 133, 263, 362} | set(range(468, 478))
    class_by_component = {}
    for ci in attached_components:
        ids = landmark_ids_by_component.get(int(ci), [])
        class_by_component[int(ci)] = "eye_or_iris" if ids and set(ids).issubset(eye_only_ids) else "facial_skin_candidate"

    # One virtual spring per compatible component pair. A candidate must be a
    # short boundary gap, have aligned surface normals, and be on components
    # carrying non-iris facial landmarks. Zero-distance seams use an isotropic
    # zero-rest Hookean tether in the solver rather than a singular direction.
    neutral_landmarks = np.asarray([(B[i][:, None] * V[T[i]]).sum(axis=0) for i in range(len(T))], dtype=np.float64)
    eye_width = float(np.linalg.norm(neutral_landmarks[263] - neutral_landmarks[33]))
    gap_limit = 0.03 * eye_width
    boundary = np.asarray(boundary, dtype=np.int64)
    tree = cKDTree(V[boundary])
    best = {}
    # Inspect only a bounded nearest-boundary neighborhood per vertex.  This
    # is still a surface-aware candidate search because distance is followed
    # by component identity and normal compatibility; it avoids materializing
    # the quadratic pair set on dense scan boundaries.
    k = max(2, int(a.boundary_k))
    distances, neighbors = tree.query(V[boundary], k=min(k + 1, len(boundary)), distance_upper_bound=gap_limit)
    if np.ndim(neighbors) == 1:
        neighbors = neighbors[:, None]
        distances = distances[:, None]
    for source_index in range(len(boundary)):
        local_v = int(boundary[source_index])
        ci = int(component_labels[local_v])
        if class_by_component.get(ci) != "facial_skin_candidate":
            continue
        for other_index, separation in zip(neighbors[source_index], distances[source_index]):
            if not np.isfinite(separation) or int(other_index) >= len(boundary):
                continue
            other_v = int(boundary[int(other_index)])
            cj = int(component_labels[other_v])
            if ci == cj or class_by_component.get(cj) != "facial_skin_candidate":
                continue
            normal_dot = float(np.dot(vertex_normal[local_v], vertex_normal[other_v]))
            if normal_dot < 0.65:
                continue
            key = tuple(sorted((ci, cj)))
            candidate = (float(separation), local_v, other_v, normal_dot)
            if key not in best or candidate[0] < best[key][0]:
                best[key] = candidate
    virtual = np.asarray([[v, w] for _, v, w, _ in best.values()], dtype=np.int64)
    virtual_rest = np.asarray([x[0] for x in best.values()], dtype=np.float64)
    virtual_normal_dot = np.asarray([x[3] for x in best.values()], dtype=np.float64)

    a.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        a.output.with_suffix(".npz"),
        V=V,
        F=F,
        originalIndices=kept_old,
        constraintTriangles=T,
        constraintBary=B,
        edgeSprings=edges,
        edgeRestLengths=rest,
        virtualSprings=virtual,
        virtualRestLengths=virtual_rest,
        componentLabels=component_labels,
        neutralLandmarks=neutral_landmarks,
    )
    graph_edges = np.vstack((edges, virtual))
    sim_graph = sparse.coo_matrix((np.ones(len(graph_edges)), (graph_edges[:, 0], graph_edges[:, 1])), shape=(len(V), len(V))).tocsr()
    sim_components, _ = connected_components(sim_graph, directed=False)
    component_records = []
    for ci in attached_components:
        ids = landmark_ids_by_component.get(int(ci), [])
        component_records.append({"component": int(ci), "vertices": int(np.sum(component_labels == ci)), "landmarks": ids, "classification": class_by_component.get(int(ci))})
    report = {
        "sourcePatch": str(a.patch),
        "sourceGoal1": str(a.goal1),
        "originalPatchVertices": int(len(V_all)),
        "simulationVertices": int(len(V)),
        "originalPatchTriangles": int(len(F_all)),
        "simulationTriangles": int(len(F)),
        "originalEdgeSprings": int(len(edges)),
        "virtualSeamSprings": int(len(virtual)),
        "virtualSpringGapLimit": gap_limit,
        "virtualSpringZeroRestCount": int(np.sum(virtual_rest < 1e-12)),
        "virtualSpringNormalDotMin": float(virtual_normal_dot.min()) if len(virtual_normal_dot) else None,
        "sourceComponents": int(component_count),
        "retainedComponents": int(len(attached_components)),
        "simulationComponentsAfterVirtualSprings": int(sim_components),
        "componentRecords": component_records,
        "classificationRule": f"retain components with Goal 1 attachments; exclude components carrying only canonical eyeball/iris IDs from seam links; inspect {k} nearest boundary candidates per vertex, then require boundary gap <= 0.03 eye widths and normal dot >= 0.65",
        "topologyChanged": False,
    }
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["simulationVertices", "simulationTriangles", "originalEdgeSprings", "virtualSeamSprings", "retainedComponents", "simulationComponentsAfterVirtualSprings"]}))


if __name__ == "__main__":
    main()
