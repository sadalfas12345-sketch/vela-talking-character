"""Two-landmark ARAP test using temporary barycentric triangle handles.

The source mesh is not changed.  Each landmark's containing triangle is split
only in a temporary computational mesh by adding a vertex at the original
barycentric point.  That inserted point is then passed to libigl's native ARAP
vertex-handle API.  All original vertices remain addressable and are used for
the post-solve barycentric measurement.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import igl
import numpy as np


def arg(name: str) -> Path:
    a = sys.argv[1:]
    return Path(a[a.index(name) + 1]).resolve()


def boundary_vertices(faces: np.ndarray) -> np.ndarray:
    counts: dict[tuple[int, int], int] = {}
    for f in faces:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            e = tuple(sorted((int(a), int(b))))
            counts[e] = counts.get(e, 0) + 1
    return np.asarray(sorted({v for e, c in counts.items() if c == 1 for v in e}), dtype=np.int32)


def split_landmark_faces(v: np.ndarray, f: np.ndarray, triangle_specs: list[dict]) -> tuple[np.ndarray, np.ndarray, dict[int, int]]:
    """Split one face per landmark and return inserted-handle vertex indices."""
    face_by_key: dict[tuple[int, int, int], int] = {}
    for fi, face in enumerate(f):
        face_by_key[tuple(sorted(map(int, face)))] = fi

    split_by_face: dict[int, list[tuple[int, np.ndarray]]] = {}
    for spec in triangle_specs:
        tri = np.asarray(spec["triangleLocal"], dtype=np.int32)
        fi_candidates = np.flatnonzero(np.all(np.isin(f, tri), axis=1))
        fi = next((int(x) for x in fi_candidates if set(map(int, f[x])) == set(map(int, tri))), None)
        if fi is None:
            raise ValueError(f"landmark {spec['id']} triangle is not present in patch")
        split_by_face.setdefault(fi, []).append((int(spec["id"]), np.asarray(spec["barycentric"], dtype=float)))

    vc = v.tolist()
    fc: list[list[int]] = []
    handles: dict[int, int] = {}
    for fi, face in enumerate(f):
        specs = split_by_face.get(fi, [])
        if not specs:
            fc.append([int(x) for x in face])
            continue
        if len(specs) != 1:
            raise ValueError(f"multiple tested landmarks share face {fi}; deterministic multi-point subdivision is not implemented")
        lid, bary = specs[0]
        base = np.asarray(face, dtype=np.int32)
        p = bary[0] * v[base[0]] + bary[1] * v[base[1]] + bary[2] * v[base[2]]
        handle = len(vc)
        vc.append(p.tolist())
        handles[lid] = handle
        fc.extend([[int(base[0]), int(base[1]), handle],
                   [int(base[1]), int(base[2]), handle],
                   [int(base[2]), int(base[0]), handle]])
    return np.asarray(vc, dtype=float), np.asarray(fc, dtype=np.int32), handles


def solve_model(model: str, patch_path: Path, goal_path: Path, marker_path: Path, out: Path) -> dict:
    p = np.load(patch_path)
    v = p["V"].astype(float)
    f = p["F"].astype(np.int32)
    original_indices = p["originalIndices"].astype(int)
    records = {int(r["index"]): r for r in json.loads(goal_path.read_text())["records"]}
    markers = json.loads(marker_path.read_text())
    targets = np.asarray(markers["samples"]["100"], dtype=float)
    neutral_markers = np.asarray(markers["neutral"], dtype=float)
    lookup = {int(x): i for i, x in enumerate(original_indices)}

    specs = []
    for lid in (70, 105):
        rec = records[lid]
        tri = np.asarray([lookup[int(x)] for x in rec["triangleVertexIndices"]], dtype=np.int32)
        bary = np.asarray(rec["barycentricCoordinates"], dtype=float)
        neutral = (bary[:, None] * v[tri]).sum(axis=0)
        requested = targets[lid] - neutral_markers[lid]
        specs.append({"id": lid, "triangleLocal": tri, "barycentric": bary,
                      "neutral": neutral, "requested": requested})

    vc, fc, handles = split_landmark_faces(v, f, specs)
    stationary = boundary_vertices(fc)
    handle_vertices = np.asarray([handles[70], handles[105]], dtype=np.int32)
    b = np.unique(np.concatenate([stationary, handle_vertices])).astype(np.int32)
    bc = vc[b].copy()
    for i, lid in enumerate((70, 105)):
        bc[np.flatnonzero(b == handles[lid])[0]] = specs[i]["neutral"] + specs[i]["requested"]

    data = igl.ARAPData()
    data.energy = igl.ARAP_ENERGY_TYPE_ELEMENTS
    data.max_iter = 100
    t0 = time.perf_counter()
    igl.arap_precomputation(vc, fc, 3, b, data)
    solved = igl.arap_solve(bc, data, vc.copy())
    runtime = time.perf_counter() - t0

    # The first len(v) vertices are exactly the original source vertices.
    original_solved = solved[: len(v)]
    base_normals = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    solved_normals = np.cross(original_solved[f[:, 1]] - original_solved[f[:, 0]],
                              original_solved[f[:, 2]] - original_solved[f[:, 0]])
    base_area2 = np.linalg.norm(base_normals, axis=1)
    solved_area2 = np.linalg.norm(solved_normals, axis=1)
    orientation_failures = np.flatnonzero(np.einsum("ij,ij->i", base_normals, solved_normals) <= 0).astype(int)
    collapsed = np.flatnonzero(solved_area2 <= base_area2 * 1e-4).astype(int)
    edges = np.unique(np.sort(np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]])), axis=1), axis=0)
    l0 = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1)
    l1 = np.linalg.norm(original_solved[edges[:, 0]] - original_solved[edges[:, 1]], axis=1)
    strains = np.abs(l1 / np.maximum(l0, 1e-20) - 1.0)

    measurements = []
    for spec in specs:
        tri = spec["triangleLocal"]
        bary = spec["barycentric"]
        achieved = (bary[:, None] * original_solved[tri]).sum(axis=0)
        actual = achieved - spec["neutral"]
        requested = spec["requested"]
        error = float(np.linalg.norm(actual - requested) / max(np.linalg.norm(requested), 1e-20))
        handle_actual = solved[handles[spec["id"]]] - spec["neutral"]
        measurements.append({"id": spec["id"], "requested": requested.tolist(),
                             "achievedFromOriginalBarycentric": actual.tolist(),
                             "barycentricError": error,
                             "insertedHandleAchieved": handle_actual.tolist(),
                             "insertedHandleError": float(np.linalg.norm(handle_actual - requested) / max(np.linalg.norm(requested), 1e-20))})

    row = {
        "model": model,
        "solver": "official libigl ARAP with temporary barycentric triangle handles",
        "landmarkIds": [70, 105],
        "sourceVertices": int(len(v)),
        "sourceTriangles": int(len(f)),
        "computationalVertices": int(len(vc)),
        "computationalTriangles": int(len(fc)),
        "insertedHandleVertices": {str(k): int(vv) for k, vv in handles.items()},
        "stationaryBoundaryVertices": int(len(stationary)),
        "runtimeSeconds": runtime,
        "measurements": measurements,
        "newInvertedTriangles": int(len(orientation_failures)),
        "invertedTriangleIds": orientation_failures.tolist(),
        "collapsedTriangles": int(len(collapsed)),
        "collapsedTriangleIds": collapsed.tolist(),
        "maximumEdgeStrain": float(np.max(strains)),
        "p95EdgeStrain": float(np.percentile(strains, 95)),
        "minimumAreaRatio": float(np.min(solved_area2 / np.maximum(base_area2, 1e-20))),
        "finite": bool(np.isfinite(original_solved).all()),
    }
    return row


def main() -> None:
    out = arg("--output")
    out.mkdir(parents=True, exist_ok=True)
    rows = [
        solve_model("female", arg("--female-patch"), arg("--female-goal"), arg("--female-markers"), out),
        solve_model("male", arg("--male-patch"), arg("--male-goal"), arg("--male-markers"), out),
    ]
    report = {"landmarkIds": [70, 105], "models": rows, "sameImplementation": True,
              "sourceGeometryModified": False, "originalVertexOrderPreserved": True}
    path = out / "results-2-subdivided-arap.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if any(any(m["barycentricError"] > 0.05 for m in r["measurements"]) or
           r["newInvertedTriangles"] or r["collapsedTriangles"] or not r["finite"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
