"""Build a connected, original-topology Plan A face patch by geodesic distance."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components, dijkstra


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mesh", type=Path, required=True)
    p.add_argument("--goal1", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--radius-eye-width", type=float, default=0.5)
    a = p.parse_args()
    z = np.load(a.mesh)
    vertices = z["V"].astype(np.float64)
    faces = z["F"].astype(np.int64)
    goal = json.loads(a.goal1.read_text(encoding="utf-8"))
    records = {int(r["index"]): r for r in goal["records"] if r.get("meshXYZ") is not None}
    if sorted(records) != list(range(478)):
        raise RuntimeError(f"Goal 1 coverage is {len(records)}/478")
    attachment_triangles = np.asarray([records[i]["triangleVertexIndices"] for i in range(478)], dtype=np.int64)
    bary = np.asarray([records[i]["barycentricCoordinates"] for i in range(478)], dtype=np.float64)
    landmark_xyz = np.asarray([records[i]["meshXYZ"] for i in range(478)], dtype=np.float64)
    eye_width = float(np.linalg.norm(landmark_xyz[263] - landmark_xyz[33]))
    seeds = np.unique(attachment_triangles.reshape(-1))

    # The graph is the original edge graph. Duplicate edges are harmless in
    # COO construction and collapsed by CSR; no render topology is changed.
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.vstack((edges, edges[:, ::-1]))
    delta = vertices[edges[:, 0]] - vertices[edges[:, 1]]
    weights = np.linalg.norm(delta, axis=1)
    graph = sparse.coo_matrix((weights, (edges[:, 0], edges[:, 1])), shape=(len(vertices), len(vertices))).tocsr()
    graph.eliminate_zeros()
    limit = float(a.radius_eye_width * eye_width)
    distances = dijkstra(graph, directed=False, indices=seeds, limit=limit, min_only=True)
    selected_vertex_mask = np.isfinite(distances)
    selected_face_mask = selected_vertex_mask[faces].any(axis=1)
    selected_faces_global = faces[selected_face_mask]
    selected_vertices_global = np.unique(selected_faces_global.reshape(-1))
    lookup = {int(v): i for i, v in enumerate(selected_vertices_global)}
    selected_faces = np.asarray([[lookup[int(v)] for v in tri] for tri in selected_faces_global], dtype=np.int64)
    constraints = []
    for i, tri in enumerate(attachment_triangles):
        if not all(int(v) in lookup for v in tri):
            raise RuntimeError(f"Attachment {i} escaped geodesic patch")
        constraints.append({"id": i, "triangle": [lookup[int(v)] for v in tri], "barycentric": bary[i].tolist(), "object": records[i].get("hitObject")})
    # Sparse component audit on the selected topology.
    local_edges = np.vstack((selected_faces[:, [0, 1]], selected_faces[:, [1, 2]], selected_faces[:, [2, 0]]))
    local_graph = sparse.coo_matrix((np.ones(len(local_edges)), (local_edges[:, 0], local_edges[:, 1])), shape=(len(selected_vertices_global), len(selected_vertices_global))).tocsr()
    component_count, labels = connected_components(local_graph, directed=False)
    edge_counts = Counter(tuple(sorted((int(x), int(y)))) for x, y in local_edges)
    boundary = sorted({v for edge, count in edge_counts.items() if count == 1 for v in edge})
    coords = vertices[selected_vertices_global]
    np.savez_compressed(
        a.output.with_suffix(".npz"),
        V=coords,
        F=selected_faces,
        originalIndices=selected_vertices_global,
        constraintTriangles=np.asarray([c["triangle"] for c in constraints], dtype=np.int64),
        constraintBary=bary,
        constraintIds=np.arange(478, dtype=np.int64),
    )
    components = []
    for ci in range(component_count):
        members = np.flatnonzero(labels == ci)
        components.append({"component": ci, "vertices": int(len(members)), "triangles": int(np.sum(np.all(labels[selected_faces] == ci, axis=1)))})
    a.output.write_text(json.dumps({
        "mesh": str(a.mesh), "goal1": str(a.goal1), "interocularWidth": eye_width,
        "radiusEyeWidth": a.radius_eye_width, "radiusModelUnits": limit,
        "sourceVertices": int(len(vertices)), "sourceTriangles": int(len(faces)),
        "solverVertices": int(len(coords)), "solverTriangles": int(len(selected_faces)),
        "connectedComponents": components, "boundaryVertices": int(len(boundary)),
        "attachmentCoverage": 478, "attachmentObjects": dict(Counter(c["object"] for c in constraints)),
        "selection": "multi-source Dijkstra over original edge graph; faces selected when incident to a vertex within the normalized radius",
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(a.output), "solverVertices": len(coords), "solverTriangles": len(selected_faces), "components": components, "boundaryVertices": len(boundary)}))


if __name__ == "__main__":
    main()
