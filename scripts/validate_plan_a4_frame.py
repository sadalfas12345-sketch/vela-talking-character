"""Validate one saved A4 geometry state against its frozen targets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--positions", type=Path, required=True)
    p.add_argument("--frame", type=int, default=-1)
    p.add_argument("--eye-width", type=float, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    g = np.load(a.graph)
    P = np.load(a.positions)["positions"].astype(float)
    target_data = np.load(a.targets)
    target = target_data["targetLandmarks"].astype(float) if "targetLandmarks" in target_data else target_data["targets"].astype(float)[a.frame]
    T = g["constraintTriangles"].astype(np.int64)
    B = g["constraintBary"].astype(float)
    V0 = g["V"].astype(float)
    actual = np.einsum("ij,ijk->ik", B, P[T])
    errors = np.linalg.norm(actual - target, axis=1)
    edge = np.vstack((g["edgeSprings"], g["virtualSprings"])).astype(np.int64)
    rest = np.concatenate((g["edgeRestLengths"], g["virtualRestLengths"])).astype(float)
    lengths = np.linalg.norm(P[edge[:, 0]] - P[edge[:, 1]], axis=1)
    positive = rest > 1e-12
    strain = np.zeros_like(lengths)
    strain[positive] = lengths[positive] / rest[positive] - 1.0
    neutral_cross = np.cross(V0[g["F"][:, 1]] - V0[g["F"][:, 0]], V0[g["F"][:, 2]] - V0[g["F"][:, 0]])
    deformed_cross = np.cross(P[g["F"][:, 1]] - P[g["F"][:, 0]], P[g["F"][:, 2]] - P[g["F"][:, 0]])
    neutral_norm = np.linalg.norm(neutral_cross, axis=1)
    deformed_norm = np.linalg.norm(deformed_cross, axis=1)
    orientation = np.einsum("ij,ij->i", neutral_cross, deformed_cross)
    collapse = (deformed_norm <= np.maximum(neutral_norm * 1e-4, 1e-15)) & (neutral_norm > 1e-15)
    report = {
        "vertices": int(len(P)),
        "triangles": int(len(g["F"])),
        "landmarks": int(len(T)),
        "maxLandmarkError": float(errors.max()) if len(errors) else 0.0,
        "maxLandmarkErrorNormalized": float(errors.max() / a.eye_width) if len(errors) else 0.0,
        "rmsLandmarkErrorNormalized": float(np.sqrt(np.mean(errors * errors)) / a.eye_width) if len(errors) else 0.0,
        "worstLandmarkIndex": int(np.argmax(errors)) if len(errors) else None,
        "maxEdgeExtension": float(np.max(strain)) if len(strain) else 0.0,
        "maxEdgeCompression": float(np.min(strain)) if len(strain) else 0.0,
        "p95AbsEdgeStrain": float(np.percentile(np.abs(strain[positive]), 95)) if np.any(positive) else 0.0,
        "invertedTriangles": int(np.sum((orientation < 0) & (neutral_norm > 1e-15))),
        "collapsedTriangles": int(np.sum(collapse)),
        "invalidCoordinates": int(np.sum(~np.isfinite(P))),
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
