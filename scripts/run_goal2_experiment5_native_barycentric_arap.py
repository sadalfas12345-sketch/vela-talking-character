"""Run Experiment 5 with exact barycentric constraints through the native bridge.

The bridge uses libigl's official ARAP precomputation, rotation fitting, ARAP
RHS, and min_quad_with_fixed sparse solver.  It adds the two barycentric
equality rows to each position update; the original Python binding cannot
expose that update hook.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from correct_goal2_experiment4_local_fold import correct, pairs, side


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


def solve_model(model: str, patch_path: Path, goal_path: Path, marker_path: Path) -> dict:
    import igl
    import libigl_barycentric_bridge as bridge

    p = np.load(patch_path)
    v = p["V"].astype(float)
    f = p["F"].astype(np.int32)
    original_indices = p["originalIndices"].astype(int)
    records = {int(r["index"]): r for r in json.loads(goal_path.read_text())["records"]}
    markers = json.loads(marker_path.read_text())
    targets = np.asarray(markers["samples"]["100"], dtype=float)
    neutral_markers = np.asarray(markers["neutral"], dtype=float)
    lookup = {int(x): i for i, x in enumerate(original_indices)}

    ids = [int(x) for x in sys.argv[sys.argv.index("--ids") + 1].split(",")] if "--ids" in sys.argv else [70, 105]
    aeq = np.zeros((len(ids), len(v)), dtype=float)
    beq = np.zeros((len(ids), 3), dtype=float)
    specs = []
    for row, lid in enumerate(ids):
        rec = records[lid]
        tri = np.asarray([lookup[int(x)] for x in rec["triangleVertexIndices"]], dtype=np.int32)
        bary = np.asarray(rec["barycentricCoordinates"], dtype=float)
        neutral = (bary[:, None] * v[tri]).sum(axis=0)
        requested = targets[lid] - neutral_markers[lid]
        aeq[row, tri] = bary
        beq[row] = neutral + requested
        specs.append({"id": lid, "tri": tri, "bary": bary, "neutral": neutral, "requested": requested})

    b = boundary_vertices(f)
    def fold_candidates(current: np.ndarray) -> list[tuple[int, int, tuple[int, int], int, int]]:
        found = []
        for ia, ib, edge, oa, ob in pairs(f):
            n = np.cross(v[f[ia][1]] - v[f[ia][0]], v[f[ia][2]] - v[f[ia][0]])
            nn = np.linalg.norm(n)
            if nn <= 1e-20:
                continue
            n /= nn
            if side(v, edge, oa, n) * side(v, edge, ob, n) < 0 and side(current, edge, oa, n) * side(current, edge, ob, n) >= 0:
                found.append((ia, ib, edge, oa, ob))
        return found

    t0 = time.perf_counter()
    solved = bridge.solve(v, f, b, aeq, beq, v.copy(), 100, 0.0, np.empty((0, 3), dtype=float))
    correction_rounds = []
    # Use the existing model-agnostic side-of-edge correction only as an
    # initializer, then re-solve the exact barycentric system. This preserves
    # the equality constraints instead of leaving a post-hoc corrected mesh.
    for _ in range(4):
        candidates = fold_candidates(solved)
        if not candidates:
            break
        corrected = solved.copy()
        changes = correct(corrected, v, f, candidates)
        corrected[b] = v[b]
        correction_rounds.append({"candidatePairs": len(candidates), "corrections": changes})
        if not changes:
            break
        solved = bridge.solve(v, f, b, aeq, beq, corrected, 100, 0.0, np.empty((0, 3), dtype=float))
    runtime = time.perf_counter() - t0

    base_normals = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    solved_normals = np.cross(solved[f[:, 1]] - solved[f[:, 0]], solved[f[:, 2]] - solved[f[:, 0]])
    base_area2 = np.linalg.norm(base_normals, axis=1)
    solved_area2 = np.linalg.norm(solved_normals, axis=1)
    orientation_failures = np.flatnonzero(np.einsum("ij,ij->i", base_normals, solved_normals) <= 0).astype(int)
    collapsed = np.flatnonzero(solved_area2 <= base_area2 * 1e-4).astype(int)
    edges = np.unique(np.sort(np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]])), axis=1), axis=0)
    l0 = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1)
    l1 = np.linalg.norm(solved[edges[:, 0]] - solved[edges[:, 1]], axis=1)
    strains = np.abs(l1 / np.maximum(l0, 1e-20) - 1.0)

    measurements = []
    for spec in specs:
        achieved = (spec["bary"][:, None] * solved[spec["tri"]]).sum(axis=0)
        actual = achieved - spec["neutral"]
        requested = spec["requested"]
        measurements.append({
            "id": spec["id"],
            "requested": requested.tolist(),
            "achievedFromOriginalBarycentric": actual.tolist(),
            "relativeError": float(np.linalg.norm(actual - requested) / max(np.linalg.norm(requested), 1e-20)),
            "constraintResidual": float(np.linalg.norm(achieved - (spec["neutral"] + requested))),
        })

    return {
        "model": model,
        "solver": "official libigl ARAP with native sparse barycentric equality constraints",
        "landmarkIds": ids,
        "patchVertices": int(len(v)),
        "patchTriangles": int(len(f)),
        "stationaryBoundaryVertices": int(len(b)),
        "runtimeSeconds": runtime,
        "correctionRounds": correction_rounds,
        "measurements": measurements,
        "newInvertedTriangles": int(len(orientation_failures)),
        "invertedTriangleIds": orientation_failures.tolist(),
        "collapsedTriangles": int(len(collapsed)),
        "collapsedTriangleIds": collapsed.tolist(),
        "maximumEdgeStrain": float(np.max(strains)),
        "p95EdgeStrain": float(np.percentile(strains, 95)),
        "minimumAreaRatio": float(np.min(solved_area2 / np.maximum(base_area2, 1e-20))),
        "finite": bool(np.isfinite(solved).all()),
    }


def main() -> None:
    out = arg("--output")
    out.mkdir(parents=True, exist_ok=True)
    rows = [
        solve_model("female", arg("--female-patch"), arg("--female-goal"), arg("--female-markers")),
        solve_model("male", arg("--male-patch"), arg("--male-goal"), arg("--male-markers")),
    ]
    ids = [int(x) for x in sys.argv[sys.argv.index("--ids") + 1].split(",")] if "--ids" in sys.argv else [70, 105]
    report = {"landmarkIds": ids, "models": rows, "sameImplementation": True,
              "sourceGeometryModified": False, "originalVertexOrderPreserved": True}
    path = out / f"results-{len(ids)}-native-barycentric-arap.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if any(any(m["relativeError"] > 0.05 for m in r["measurements"]) or
           r["newInvertedTriangles"] or r["collapsedTriangles"] or not r["finite"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
