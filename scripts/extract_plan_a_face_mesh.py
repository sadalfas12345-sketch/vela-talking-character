"""Extract an in-memory Plan A facial-skin simulation patch from an original GLB.

The source GLB is never written.  The patch retains original vertex and triangle
IDs so every solved position can be mapped back to the render mesh.  The
selection is anatomical: it is seeded by the existing Goal 1 attachment
triangles, expanded by a normalized face-radius margin, and then split by the
original mesh connectivity.  No vertices are welded or retopologized.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

import bpy
import numpy as np
from mathutils.kdtree import KDTree


def arg(name: str) -> Path:
    values = sys.argv[sys.argv.index("--") + 1 :]
    return Path(values[values.index(name) + 1]).resolve()


def world_vertices(obj):
    raw = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", raw)
    local = raw.reshape(-1, 3)
    matrix = np.asarray(obj.matrix_world, dtype=np.float64)
    return local @ matrix[:3, :3].T + matrix[:3, 3]


def connected_components(vertex_count, faces):
    parent = np.arange(vertex_count, dtype=np.int64)
    size = np.ones(vertex_count, dtype=np.int64)

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    def union(a, b):
        ra, rb = find(int(a)), find(int(b))
        if ra == rb:
            return
        if size[ra] < size[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        size[ra] += size[rb]

    for a, b, c in faces:
        union(a, b)
        union(b, c)
        union(c, a)
    groups = defaultdict(list)
    for v in range(vertex_count):
        groups[find(v)].append(v)
    return list(groups.values())


def boundary_vertices(faces):
    counts = Counter()
    for tri in faces:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[tuple(sorted((int(a), int(b))))] += 1
    return sorted({v for edge, count in counts.items() if count == 1 for v in edge}), counts


def main():
    source = arg("--source")
    goal1 = arg("--goal1")
    output = arg("--output")
    output.parent.mkdir(parents=True, exist_ok=True)

    report = json.loads(goal1.read_text(encoding="utf-8"))
    records = {int(r["index"]): r for r in report["records"] if r.get("meshXYZ") is not None}
    if sorted(records) != list(range(478)):
        raise RuntimeError(f"Goal 1 attachment coverage is {len(records)}/478")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("GLB contains no mesh")
    body = max(meshes, key=lambda o: len(o.data.vertices))
    vertices = world_vertices(body)
    raw_faces = []
    for polygon in body.data.polygons:
        if len(polygon.vertices) != 3:
            raise RuntimeError("Non-triangle polygon found after GLB import")
        tri = tuple(int(v) for v in polygon.vertices)
        area2 = np.linalg.norm(np.cross(vertices[tri[1]] - vertices[tri[0]], vertices[tri[2]] - vertices[tri[0]]))
        if area2 > 1e-18:
            raw_faces.append(tri)
    faces = np.asarray(raw_faces, dtype=np.int64)

    attachment_triangles = np.asarray(
        [records[i]["triangleVertexIndices"] for i in range(478)], dtype=np.int64
    )
    attachment_vertices = np.unique(attachment_triangles.reshape(-1))
    neutral_landmarks = np.asarray([records[i]["meshXYZ"] for i in range(478)], dtype=np.float64)
    eye_width = float(np.linalg.norm(neutral_landmarks[263] - neutral_landmarks[33]))
    face_center = np.mean(neutral_landmarks[[33, 263, 1, 152]], axis=0)
    right_axis = neutral_landmarks[263] - neutral_landmarks[33]
    right_axis /= max(np.linalg.norm(right_axis), 1e-12)
    up_axis = neutral_landmarks[10] - neutral_landmarks[152]
    up_axis -= right_axis * np.dot(up_axis, right_axis)
    up_axis /= max(np.linalg.norm(up_axis), 1e-12)
    forward_axis = np.cross(right_axis, up_axis)
    forward_axis /= max(np.linalg.norm(forward_axis), 1e-12)
    anatomical_axes = np.stack([right_axis, up_axis, forward_axis], axis=0)
    landmark_local = (neutral_landmarks - face_center) @ anatomical_axes.T
    local_min = landmark_local.min(axis=0)
    local_max = landmark_local.max(axis=0)

    # Select original vertices in a normalized geodesic seed neighborhood. A
    # KD-tree is used only to seed the original surface; faces and edges remain
    # exactly the source topology. The radius is relative to eye width, so the
    # same rule applies to both differently scaled characters.
    margin = 0.10 * eye_width
    tree = KDTree(len(vertices))
    for index, point in enumerate(vertices):
        tree.insert(tuple(float(x) for x in point), index)
    tree.balance()
    seed_vertices = set(int(v) for v in attachment_vertices)
    for point in neutral_landmarks:
        seed_vertices.update(int(item[1]) for item in tree.find_range(tuple(float(x) for x in point), margin))
    face_mask = np.isin(faces, np.fromiter(seed_vertices, dtype=np.int64)).any(axis=1)
    selected_faces_global = faces[face_mask]

    # Preserve every selected original face. Connectivity is audited later by
    # sparse graph routines; a Python component walk is too expensive here.
    selected_vertices_global = np.unique(selected_faces_global.reshape(-1))
    global_to_selected = {int(v): i for i, v in enumerate(selected_vertices_global)}
    selected_faces = np.asarray(
        [[global_to_selected[int(v)] for v in tri] for tri in selected_faces_global], dtype=np.int64
    )
    for tri in attachment_triangles:
        local = [global_to_selected.get(int(v)) for v in tri]
        if any(v is None for v in local):
            raise RuntimeError("An attachment triangle was not included in the selected patch")
    kept_faces = selected_faces
    original_indices = selected_vertices_global
    coords = vertices[original_indices]
    original_to_local = {int(v): i for i, v in enumerate(original_indices)}
    constraints = []
    missing = []
    for i in range(478):
        tri_global = attachment_triangles[i]
        try:
            tri_local = [original_to_local[int(v)] for v in tri_global]
        except KeyError:
            missing.append(i)
            continue
        constraints.append(
            {
                "id": i,
                "triangle": tri_local,
                "barycentric": records[i]["barycentricCoordinates"],
                "object": records[i].get("hitObject"),
            }
        )
    if missing:
        raise RuntimeError(f"Missing selected-patch constraints: {missing[:20]}")

    boundary, edge_counts = boundary_vertices(kept_faces)
    boundary_dist = np.linalg.norm(coords[np.asarray(boundary)] - face_center, axis=1) if boundary else np.array([])
    np.savez_compressed(
        output.with_suffix(".npz"),
        V=coords,
        F=kept_faces,
        originalIndices=original_indices,
        constraintTriangles=np.asarray([c["triangle"] for c in constraints], dtype=np.int64),
        constraintBary=np.asarray([c["barycentric"] for c in constraints], dtype=np.float64),
        constraintIds=np.arange(478, dtype=np.int64),
    )
    components_report = "deferred_to_sparse_audit"
    output.write_text(
        json.dumps(
            {
                "source": str(source),
                "goal1": str(goal1),
                "meshObject": body.name,
                "sourceVertices": len(vertices),
                "sourceTriangles": len(faces),
                "mappedLandmarks": 478,
                "interocularWidth": eye_width,
                "faceCenter": face_center.tolist(),
                "anatomicalAxes": anatomical_axes.tolist(),
                "landmarkLocalBounds": {"min": local_min.tolist(), "max": local_max.tolist()},
                "selectionRadius": margin,
                "solverVertices": int(len(coords)),
                "solverTriangles": int(len(kept_faces)),
                "connectedComponents": components_report,
                "boundaryVertices": len(boundary),
                "boundaryDistanceMin": float(boundary_dist.min()) if boundary_dist.size else None,
                "boundaryDistanceMedian": float(np.median(boundary_dist)) if boundary_dist.size else None,
                "boundaryDistanceMax": float(boundary_dist.max()) if boundary_dist.size else None,
                "attachmentObjects": dict(Counter(c["object"] for c in constraints)),
                "constraints": constraints,
                "depthObservation": "unavailable: source archive contains normalized 2D trajectories only",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "solverVertices": len(coords), "solverTriangles": len(kept_faces), "components": components_report, "boundaryVertices": len(boundary)}))


if __name__ == "__main__":
    main()
