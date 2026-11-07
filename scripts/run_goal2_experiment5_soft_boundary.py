"""Compare rigid and stiffness-normalized soft boundaries for landmark 105."""
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


def measure(v: np.ndarray, f: np.ndarray, u: np.ndarray, b: np.ndarray, eye: float, neutral: np.ndarray, tri: np.ndarray, bary: np.ndarray, target: np.ndarray) -> dict:
    n0 = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n1 = np.cross(u[f[:, 1]] - u[f[:, 0]], u[f[:, 2]] - u[f[:, 0]])
    a0, a1 = np.linalg.norm(n0, axis=1) * .5, np.linalg.norm(n1, axis=1) * .5
    flips = np.flatnonzero(np.einsum("ij,ij->i", n0, n1) <= 0)
    collapsed = np.flatnonzero(a1 <= a0 * 1e-4)
    edges = np.unique(np.sort(np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]])), axis=1), axis=0)
    l0 = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1)
    l1 = np.linalg.norm(u[edges[:, 0]] - u[edges[:, 1]], axis=1)
    strain = np.abs(l1 / np.maximum(l0, 1e-20) - 1.0)
    achieved = (bary[:, None] * u[tri]).sum(axis=0)
    return {
        "landmarkError": float(np.linalg.norm(achieved - target) / max(np.linalg.norm(target - neutral), 1e-20)),
        "newInvertedTriangles": int(len(flips)),
        "invertedTriangleIds": flips.tolist(),
        "collapsedTriangles": int(len(collapsed)),
        "maximumEdgeStrain": float(np.max(strain)),
        "p95EdgeStrain": float(np.percentile(strain, 95)),
        "maximumBoundaryDisplacement": float(np.max(np.linalg.norm(u[b] - v[b], axis=1))),
        "maximumBoundaryDisplacementPercentEyeWidth": float(np.max(np.linalg.norm(u[b] - v[b], axis=1)) / eye),
        "minimumAreaRatio": float(np.min(a1 / np.maximum(a0, 1e-20))),
        "finite": bool(np.isfinite(u).all()),
    }


def run_model(model: str, patch_path: Path, goal_path: Path, marker_path: Path, bridge, configs: list[tuple[str, float | None, float]]) -> dict:
    p = np.load(patch_path)
    v, f, orig = p["V"].astype(float), p["F"].astype(np.int32), p["originalIndices"].astype(int)
    lookup = {int(x): i for i, x in enumerate(orig)}
    records = {int(r["index"]): r for r in json.loads(goal_path.read_text())["records"]}
    markers = json.loads(marker_path.read_text())
    targets = np.asarray(markers["samples"]["100"], dtype=float)
    neutral_markers = np.asarray(markers["neutral"], dtype=float)
    tri = np.asarray([lookup[int(x)] for x in records[105]["triangleVertexIndices"]], dtype=np.int32)
    bary = np.asarray(records[105]["barycentricCoordinates"], dtype=float)
    neutral = (bary[:, None] * v[tri]).sum(axis=0)
    requested = targets[105] - neutral_markers[105]
    target = neutral + requested
    eye = float(np.linalg.norm(np.asarray(records[33]["meshXYZ"]) - np.asarray(records[263]["meshXYZ"])))
    b = boundary_vertices(f)
    q = (-igl.cotmatrix(v, f)).tocsc()
    scale = float(np.median(np.abs(q.diagonal()[q.diagonal() != 0])))
    rows = []
    aeq = np.zeros((1, len(v)), dtype=float)
    aeq[0, tri] = bary
    beq = target[None, :]
    for name, factor, expected_penalty in configs:
        penalty = 0.0 if factor is None else factor * scale
        t0 = time.perf_counter()
        if factor is None:
            u = bridge.solve(v, f, b, aeq, beq, v.copy(), 100, 0.0, np.empty((0, 3), dtype=float))
        else:
            u = bridge.solve(v, f, b, aeq, beq, v.copy(), 100, penalty, v[b].copy())
        elapsed = time.perf_counter() - t0
        row = measure(v, f, u, b, eye, neutral, tri, bary, target)
        row.update({"model": model, "boundaryConfiguration": name, "stiffnessFactor": factor, "boundaryPenalty": penalty, "referenceScale": scale, "runtimeSeconds": elapsed, "requestedDisplacement": requested.tolist(), "requestedMagnitude": float(np.linalg.norm(requested)), "patchVertices": int(len(v)), "patchTriangles": int(len(f))})
        rows.append(row)
    return {"model": model, "landmark105Attachment": {"triangleVertexIds": records[105]["triangleVertexIndices"], "barycentricWeights": records[105]["barycentricCoordinates"], "neutralPosition": neutral.tolist(), "targetPosition": target.tolist(), "interocularWidth": eye}, "results": rows}


def main() -> None:
    import libigl_barycentric_bridge as bridge
    out = arg("--output")
    out.mkdir(parents=True, exist_ok=True)
    configs = [("rigid", None, 0.0), ("strong-soft", 100.0, 0.0), ("medium-soft", 10.0, 0.0), ("weak-soft", 1.0, 0.0)]
    report = {"boundaryPenalty": "lambda * sum ||U_boundary - V0_boundary||^2", "stiffnessScale": "median nonzero diagonal of -cotmatrix", "sameAlgorithm": True, "models": [
        run_model("female", arg("--female-patch"), arg("--female-goal"), arg("--female-markers"), bridge, configs),
        run_model("male", arg("--male-patch"), arg("--male-goal"), arg("--male-markers"), bridge, configs),
    ]}
    (out / "soft-boundary-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
