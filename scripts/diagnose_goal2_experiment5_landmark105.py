"""Diagnose why Goal-1 landmark 105 folds under exact native ARAP."""
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
    for f in faces:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            e = tuple(sorted((int(a), int(b))))
            counts[e] = counts.get(e, 0) + 1
    return np.asarray(sorted({v for e, c in counts.items() if c == 1 for v in e}), dtype=np.int32)


def edge_array(f: np.ndarray) -> np.ndarray:
    return np.unique(np.sort(np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]])), axis=1), axis=0)


def solve_case(bridge, v, f, recs, targets, neutral_markers, case: str) -> tuple[np.ndarray, dict]:
    lookup = recs["lookup"]
    tri70 = np.asarray([lookup[int(x)] for x in recs[70]["triangleVertexIndices"]], dtype=np.int32)
    tri105 = np.asarray([lookup[int(x)] for x in recs[105]["triangleVertexIndices"]], dtype=np.int32)
    b70 = np.asarray(recs[70]["barycentricCoordinates"], dtype=float)
    b105 = np.asarray(recs[105]["barycentricCoordinates"], dtype=float)
    n70 = (b70[:, None] * v[tri70]).sum(axis=0)
    n105 = (b105[:, None] * v[tri105]).sum(axis=0)
    d70 = targets[70] - neutral_markers[70]
    d105 = targets[105] - neutral_markers[105]

    if case == "A":
        lid, tri, bary, neutral, displacement = 105, tri105, b105, n105, d105
    elif case == "B":
        lid, tri, bary, neutral, displacement = 105, tri105, b105, n105, d70
    elif case == "C":
        lid, tri, bary, neutral, displacement = 70, tri70, b70, n70, d105
    else:
        raise ValueError(case)

    aeq = np.zeros((1, len(v)), dtype=float)
    aeq[0, tri] = bary
    beq = (neutral + displacement)[None, :]
    b = boundary_vertices(f)
    t0 = time.perf_counter()
    solved = bridge.solve(v, f, b, aeq, beq, v.copy(), 100)
    runtime = time.perf_counter() - t0

    base_n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    deformed_n = np.cross(solved[f[:, 1]] - solved[f[:, 0]], solved[f[:, 2]] - solved[f[:, 0]])
    area0 = np.linalg.norm(base_n, axis=1) * 0.5
    area1 = np.linalg.norm(deformed_n, axis=1) * 0.5
    flipped = np.flatnonzero(np.einsum("ij,ij->i", base_n, deformed_n) <= 0).astype(int)
    collapsed = np.flatnonzero(area1 <= area0 * 1e-4).astype(int)
    edges = edge_array(f)
    l0 = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1)
    l1 = np.linalg.norm(solved[edges[:, 0]] - solved[edges[:, 1]], axis=1)
    strain = np.abs(l1 / np.maximum(l0, 1e-20) - 1.0)
    achieved = (bary[:, None] * solved[tri]).sum(axis=0)
    base_landmark = neutral
    requested_error = float(np.linalg.norm((achieved - base_landmark) - displacement) / max(np.linalg.norm(displacement), 1e-20))
    boundary_points = v[b]
    triangle_points = v[f[flipped]] if len(flipped) else np.empty((0, 3))
    damaged = []
    for fi in flipped.tolist():
        face = f[fi]
        neutral_edges = [float(np.linalg.norm(v[face[(j + 1) % 3]] - v[face[j]])) for j in range(3)]
        deformed_edges = [float(np.linalg.norm(solved[face[(j + 1) % 3]] - solved[face[j]])) for j in range(3)]
        damaged.append({
            "localTriangleId": int(fi),
            "originalVertexIds": [int(x) for x in recs["originalIndices"][face]],
            "distanceFromControlledLandmark": float(np.min(np.linalg.norm(v[face] - neutral, axis=1))),
            "distanceFromPatchBoundary": float(np.min(np.linalg.norm(v[face][:, None, :] - boundary_points[None, :, :], axis=2))),
            "neutralArea": float(area0[fi]),
            "deformedArea": float(area1[fi]),
            "neutralEdgeLengths": neutral_edges,
            "deformedEdgeLengths": deformed_edges,
            "vertexDisplacements": [np.asarray(solved[x] - v[x]).tolist() for x in face],
        })

    row = {
        "case": case,
        "controlledLandmark": int(lid),
        "requestedDisplacement": displacement.tolist(),
        "requestedMagnitude": float(np.linalg.norm(displacement)),
        "requestedPercentOfInterocular": float(np.linalg.norm(displacement) / recs["eyeWidth"]),
        "achievedDisplacement": (achieved - base_landmark).tolist(),
        "landmarkRelativeError": requested_error,
        "runtimeSeconds": runtime,
        "newInvertedTriangles": int(len(flipped)),
        "newCollapsedTriangles": int(len(collapsed)),
        "invertedTriangleIds": flipped.tolist(),
        "maximumEdgeStrain": float(np.max(strain)),
        "p95EdgeStrain": float(np.percentile(strain, 95)),
        "maximumFreeVertexMovement": float(np.max(np.linalg.norm(solved - v, axis=1))),
        "damagedTriangles": damaged,
        "finite": bool(np.isfinite(solved).all()),
    }
    return solved, row


def diagnostic_plot(out: Path, model: str, v: np.ndarray, f: np.ndarray, solved: np.ndarray, row: dict, neutral: np.ndarray, target: np.ndarray, attachment: np.ndarray) -> None:
    try:
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except Exception:
        return
    # Plot the nearest 160 triangles to the controlled attachment, plus all
    # damaged triangles, so the image remains a readable local close-up.
    centroids = v[f].mean(axis=1)
    order = np.argsort(np.linalg.norm(centroids - neutral, axis=1))[:160]
    chosen = set(map(int, order.tolist())) | set(row["invertedTriangleIds"])
    fig = plt.figure(figsize=(8, 8), dpi=160)
    ax = fig.add_subplot(111, projection="3d")
    for fi in chosen:
        poly = Poly3DCollection([v[f[fi]]], alpha=0.08, facecolor="steelblue", edgecolor="0.45")
        ax.add_collection3d(poly)
        if fi in set(row["invertedTriangleIds"]):
            ax.add_collection3d(Poly3DCollection([solved[f[fi]]], alpha=0.5, facecolor="red", edgecolor="black"))
    ax.scatter(*neutral, c="lime", s=35, label="neutral")
    ax.scatter(*target, c="yellow", s=35, label="target")
    ax.scatter(*attachment, c="magenta", s=35, label="achieved")
    pts = np.vstack([v[f[list(chosen)]].reshape(-1, 3), neutral, target, attachment])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    mid = (lo + hi) / 2.0
    radius = max((hi - lo).max() / 2.0, 1e-6)
    ax.set_xlim(mid[0] - radius, mid[0] + radius)
    ax.set_ylim(mid[1] - radius, mid[1] + radius)
    ax.set_zlim(mid[2] - radius, mid[2] + radius)
    ax.set_title(f"{model} landmark 105 diagnostic case {row['case']}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    import igl  # noqa: F401
    import libigl_barycentric_bridge as bridge
    out = arg("--output")
    out.mkdir(parents=True, exist_ok=True)
    models = [
        ("female", arg("--female-patch"), arg("--female-goal"), arg("--female-markers")),
        ("male", arg("--male-patch"), arg("--male-goal"), arg("--male-markers")),
    ]
    all_rows = []
    for model, patch_path, goal_path, marker_path in models:
        p = np.load(patch_path)
        v, f = p["V"].astype(float), p["F"].astype(np.int32)
        original_indices = p["originalIndices"].astype(int)
        records = {int(r["index"]): r for r in json.loads(goal_path.read_text())["records"]}
        records["lookup"] = {int(x): i for i, x in enumerate(original_indices)}
        records["originalIndices"] = original_indices
        records["eyeWidth"] = float(np.linalg.norm(np.asarray(records[33]["meshXYZ"]) - np.asarray(records[263]["meshXYZ"])))
        markers = json.loads(marker_path.read_text())
        targets = np.asarray(markers["samples"]["100"], dtype=float)
        neutral_markers = np.asarray(markers["neutral"], dtype=float)
        adjacent = {}
        for lid in (63, 70, 105):
            rec = records[lid]
            tri = np.asarray([records["lookup"][int(x)] for x in rec["triangleVertexIndices"]], dtype=np.int32)
            bary = np.asarray(rec["barycentricCoordinates"], dtype=float)
            attached_neutral = (bary[:, None] * v[tri]).sum(axis=0)
            adjacent[str(lid)] = {
                "triangleVertexIds": rec["triangleVertexIndices"],
                "triangleLocalIndices": tri.tolist(),
                "barycentricWeights": rec["barycentricCoordinates"],
                "attachedNeutralPosition": attached_neutral.tolist(),
                "goal1RecordedPosition": rec.get("meshXYZ"),
                "targetPosition": targets[lid].tolist(),
                "requestedDisplacement": (targets[lid] - neutral_markers[lid]).tolist(),
                "requestedMagnitude": float(np.linalg.norm(targets[lid] - neutral_markers[lid])),
                "requestedPercentOfInterocular": float(np.linalg.norm(targets[lid] - neutral_markers[lid]) / records["eyeWidth"]),
            }
        model_rows = []
        for case in ("A", "B", "C"):
            solved, row = solve_case(bridge, v, f, records, targets, neutral_markers, case)
            control_id = row["controlledLandmark"]
            rec = records[control_id]
            tri = np.asarray([records["lookup"][int(x)] for x in rec["triangleVertexIndices"]], dtype=np.int32)
            bary = np.asarray(rec["barycentricCoordinates"], dtype=float)
            neutral = (bary[:, None] * v[tri]).sum(axis=0)
            achieved = (bary[:, None] * solved[tri]).sum(axis=0)
            target = neutral + np.asarray(row["requestedDisplacement"])
            diagnostic_plot(out / f"{model}-case-{case}-landmark-{control_id}.png", model, v, f, solved, row, neutral, target, achieved)
            np.savez_compressed(out / f"{model}-case-{case}-solution.npz", V=v, U=solved, F=f, originalIndices=original_indices)
            model_rows.append(row)
        all_rows.append({"model": model, "adjacentLandmarks": adjacent, "landmark105Attachment": {
            "meshObject": records[105].get("meshObject"),
            "triangleVertexIds": records[105]["triangleVertexIndices"],
            "triangleLocalIndices": [int(records["lookup"][int(x)]) for x in records[105]["triangleVertexIndices"]],
            "barycentricWeights": records[105]["barycentricCoordinates"],
            "neutralPosition": ((np.asarray(records[105]["barycentricCoordinates"])[:, None] * v[[records["lookup"][int(x)] for x in records[105]["triangleVertexIndices"]]]).sum(axis=0)).tolist(),
            "targetPosition": targets[105].tolist(),
            "requestedDisplacement": (targets[105] - neutral_markers[105]).tolist(),
            "requestedMagnitude": float(np.linalg.norm(targets[105] - neutral_markers[105])),
            "interocularWidth": records["eyeWidth"],
            "requestedPercentOfInterocular": float(np.linalg.norm(targets[105] - neutral_markers[105]) / records["eyeWidth"]),
        }, "landmark70Displacement": (targets[70] - neutral_markers[70]).tolist(), "cases": model_rows})
    report = {"models": all_rows, "sameImplementation": True, "targetsModified": False, "goal1Modified": False}
    (out / "landmark105-diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
