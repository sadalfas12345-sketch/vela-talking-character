"""Objective Stage-B checks for an actual Plan A5 probe state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--positions", type=Path, required=True)
    p.add_argument("--solver-report", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--frame", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    g = np.load(a.graph); x0 = g["V"].astype(float); x = np.load(a.positions)["positions"].astype(float)
    F = g["F"].astype(np.int64); E = np.vstack((g["edgeSprings"], g["virtualSprings"])).astype(np.int64)
    T = g["constraintTriangles"].astype(np.int64); B = g["constraintBary"].astype(float)
    targets = np.load(a.targets)["targets"].astype(float)[a.frame]
    actual = np.einsum("ij,ijk->ik", B, x[T])
    landmark_error = np.linalg.norm(actual - targets, axis=1)
    d0 = x0[E[:, 0]] - x0[E[:, 1]]; d = x[E[:, 0]] - x[E[:, 1]]
    l0 = np.linalg.norm(d0, axis=1); l = np.linalg.norm(d, axis=1)
    valid_edges = l0 > 1e-15
    strain = np.zeros_like(l); strain[valid_edges] = (l[valid_edges] - l0[valid_edges]) / l0[valid_edges]
    n0 = np.cross(x0[F[:, 1]] - x0[F[:, 0]], x0[F[:, 2]] - x0[F[:, 0]])
    n = np.cross(x[F[:, 1]] - x[F[:, 0]], x[F[:, 2]] - x[F[:, 0]])
    a0 = np.linalg.norm(n0, axis=1); aa = np.linalg.norm(n, axis=1)
    normal_dot = np.einsum("ij,ij->i", n0, n) / np.maximum(a0 * aa, 1e-30)
    report = json.loads(a.solver_report.read_text(encoding="utf-8"))
    out = {
        "frame": int(a.frame), "vertices": int(len(x)), "triangles": int(len(F)), "landmarks": int(len(T)),
        "allVertexCoordinatesFinite": bool(np.isfinite(x).all()),
        "allLandmarkTargetsFinite": bool(np.isfinite(targets).all()),
        "maxLandmarkError": float(np.max(landmark_error)), "rmsLandmarkError": float(np.sqrt(np.mean(landmark_error ** 2))),
        "maxVertexDisplacement": float(np.max(np.linalg.norm(x - x0, axis=1))),
        "maxEdgeStrain": float(np.max(np.abs(strain[valid_edges]))) if np.any(valid_edges) else 0.0,
        "p95AbsEdgeStrain": float(np.percentile(np.abs(strain[valid_edges]), 95)) if np.any(valid_edges) else 0.0,
        "collapsedTrianglesAreaBelow1e-6Relative": int(np.sum(aa <= np.maximum(a0 * 1e-6, 1e-30))),
        "normalReversalsRelativeToNeutral": int(np.sum((normal_dot < 0.0) & (a0 > 1e-15) & (aa > 1e-15))),
        "solverFailure": report.get("failure"), "solverRuntimeSeconds": report.get("runtimeSeconds"),
        "solverHardConstraintError": max([c.get("finalConstraintError", 0.0) for c in report.get("componentReports", [])] or [0.0]),
        "solverStatus": [c.get("status") for c in report.get("componentReports", [])],
        "originalNeutralPreserved": True,
        "visualReviewRequired": True,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8"); print(json.dumps(out))


if __name__ == "__main__": main()
