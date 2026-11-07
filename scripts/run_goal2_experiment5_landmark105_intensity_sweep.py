"""Sweep landmark 105 from neutral to its existing peak target.

Each intensity starts from the original neutral patch and uses the existing
native libigl ARAP barycentric bridge with the fixed original boundary.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np


def arg(name: str) -> Path:
    a = sys.argv[1:]
    return Path(a[a.index(name) + 1]).resolve()


def boundary_vertices(faces: np.ndarray) -> np.ndarray:
    counts: dict[tuple[int, int], int] = {}
    for face in faces:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge = tuple(sorted((int(a), int(b))))
            counts[edge] = counts.get(edge, 0) + 1
    return np.asarray(sorted({v for e, c in counts.items() if c == 1 for v in e}), dtype=np.int32)


def solve_one(model: str, patch_path: Path, goal_path: Path, marker_path: Path, out: Path) -> dict:
    import libigl_barycentric_bridge as bridge

    p = np.load(patch_path)
    v = p["V"].astype(float)
    f = p["F"].astype(np.int32)
    original_indices = p["originalIndices"].astype(int)
    lookup = {int(x): i for i, x in enumerate(original_indices)}
    records = {int(r["index"]): r for r in json.loads(goal_path.read_text())["records"]}
    markers = json.loads(marker_path.read_text())
    peak = np.asarray(markers["samples"]["100"], dtype=float)
    neutral_markers = np.asarray(markers["neutral"], dtype=float)
    rec = records[105]
    tri = np.asarray([lookup[int(x)] for x in rec["triangleVertexIndices"]], dtype=np.int32)
    bary = np.asarray(rec["barycentricCoordinates"], dtype=float)
    neutral = (bary[:, None] * v[tri]).sum(axis=0)
    requested = peak[105] - neutral_markers[105]
    target_peak = neutral + requested
    boundary = boundary_vertices(f)
    aeq = np.zeros((1, len(v)), dtype=float)
    aeq[0, tri] = bary
    base_n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    base_area = np.linalg.norm(base_n, axis=1)
    edges = np.unique(np.sort(np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]])), axis=1), axis=0)
    base_l = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1)
    eye = float(np.linalg.norm(np.asarray(records[33]["meshXYZ"]) - np.asarray(records[263]["meshXYZ"])))
    rows = []
    snapshots = {}
    for percent in range(0, 101):
        frac = percent / 100.0
        target = neutral + frac * requested
        t0 = time.perf_counter()
        solved = bridge.solve(v, f, boundary, aeq, target[None, :], v.copy(), 100, 0.0, np.empty((0, 3), dtype=float))
        runtime = time.perf_counter() - t0
        deformed_n = np.cross(solved[f[:, 1]] - solved[f[:, 0]], solved[f[:, 2]] - solved[f[:, 0]])
        deformed_area = np.linalg.norm(deformed_n, axis=1)
        dots = np.einsum("ij,ij->i", base_n, deformed_n)
        folds = np.flatnonzero(dots <= 0).astype(int)
        collapsed = np.flatnonzero(deformed_area <= base_area * 1e-4).astype(int)
        lengths = np.linalg.norm(solved[edges[:, 0]] - solved[edges[:, 1]], axis=1)
        strain = np.abs(lengths / np.maximum(base_l, 1e-20) - 1.0)
        achieved = (bary[:, None] * solved[tri]).sum(axis=0)
        actual = achieved - neutral
        distance = np.linalg.norm(((v[f[folds]]).mean(axis=1) - neutral), axis=1) if len(folds) else np.empty(0)
        tri_details = []
        for fid, dist in zip(folds, distance):
            tri_details.append({
                "localTriangleId": int(fid),
                "originalVertexIds": original_indices[f[int(fid)]].astype(int).tolist(),
                "distanceFromLandmark": float(dist),
                "neutralArea": float(base_area[fid] * 0.5),
                "deformedArea": float(deformed_area[fid] * 0.5),
                "normalDot": float(dots[fid]),
            })
        row = {
            "intensityPercent": percent,
            "requestedDisplacement": (frac * requested).tolist(),
            "requestedMagnitude": float(np.linalg.norm(frac * requested)),
            "achievedDisplacement": actual.tolist(),
            "landmarkRelativeError": float(np.linalg.norm(actual - frac * requested) / max(np.linalg.norm(frac * requested), 1e-20)) if percent else 0.0,
            "landmarkConstraintResidual": float(np.linalg.norm(achieved - target)),
            "newGenuineFolds": int(len(folds)),
            "foldedTriangles": tri_details,
            "collapsedTriangles": int(len(collapsed)),
            "collapsedTriangleIds": collapsed.tolist(),
            "maximumEdgeStrain": float(np.max(strain)),
            "p95EdgeStrain": float(np.percentile(strain, 95)),
            "minimumAreaRatio": float(np.min(deformed_area / np.maximum(base_area, 1e-20))),
            "finite": bool(np.isfinite(solved).all()),
            "runtimeSeconds": runtime,
        }
        rows.append(row)
        if len(folds) and "first" not in snapshots:
            snapshots["first"] = {"percent": percent, "V": solved, "foldIds": folds}
        if percent == 0:
            snapshots["neutral"] = {"percent": 0, "V": solved, "foldIds": folds}
        if percent == 100:
            snapshots["peak"] = {"percent": 100, "V": solved, "foldIds": folds}
    onset = next((r["intensityPercent"] for r in rows if r["newGenuineFolds"]), None)
    npz_values = {"V_neutral": snapshots["neutral"]["V"], "V_peak": snapshots["peak"]["V"], "F": f, "originalIndices": original_indices}
    if "first" in snapshots:
        npz_values["V_firstFold"] = snapshots["first"]["V"]
        npz_values["firstFoldIds"] = snapshots["first"]["foldIds"]
        npz_values["firstFoldPercent"] = np.asarray([snapshots["first"]["percent"]])
    np.savez_compressed(out / f"{model}-intensity-snapshots.npz", **npz_values)
    return {
        "model": model,
        "landmarkId": 105,
        "triangleVertexIds": rec["triangleVertexIndices"],
        "barycentricWeights": rec["barycentricCoordinates"],
        "neutralPosition": neutral.tolist(),
        "peakTargetPosition": target_peak.tolist(),
        "requestedPeakDisplacement": requested.tolist(),
        "requestedPeakMagnitude": float(np.linalg.norm(requested)),
        "interocularWidth": eye,
        "patchVertices": int(len(v)),
        "patchTriangles": int(len(f)),
        "boundaryVertices": int(len(boundary)),
        "firstFoldOnsetPercent": onset,
        "results": rows,
    }


def main() -> None:
    out = arg("--output")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "solver": "official libigl ARAP with exact barycentric landmark equality and fixed original boundary",
        "sourceGeometryModified": False,
        "sameImplementation": True,
        "models": [
            solve_one("female", arg("--female-patch"), arg("--female-goal"), arg("--female-markers"), out),
            solve_one("male", arg("--male-patch"), arg("--male-goal"), arg("--male-markers"), out),
        ],
    }
    (out / "landmark105-intensity-sweep.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
