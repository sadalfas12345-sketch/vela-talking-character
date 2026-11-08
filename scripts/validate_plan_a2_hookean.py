"""Independent numerical validation of a Plan A2 Hookean trajectory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    g = np.load(a.graph)
    z = np.load(a.run.with_name(a.run.stem + "-positions.npz"))
    positions = z["positions"].astype(float)
    neutral = g["V"].astype(float)
    F = g["F"].astype(np.int64)
    T = g["constraintTriangles"].astype(np.int64)
    B = g["constraintBary"].astype(float)
    targets = np.load(a.targets)["targets"].astype(float)[: len(positions)]
    edges = np.vstack((g["edgeSprings"].astype(np.int64), g["virtualSprings"].astype(np.int64)))
    rest = np.concatenate((g["edgeRestLengths"].astype(float), g["virtualRestLengths"].astype(float)))
    eye = float(np.linalg.norm(np.asarray(g["neutralLandmarks"])[263] - np.asarray(g["neutralLandmarks"])[33]))
    landmark_errors = []
    edge_rows = []
    tri_rows = []
    for fi, x in enumerate(positions):
        actual = np.einsum("ij,ijk->ik", B, x[T])
        err = np.linalg.norm(actual - targets[fi], axis=1)
        landmark_errors.append(err)
        lengths = np.linalg.norm(x[edges[:, 0]] - x[edges[:, 1]], axis=1)
        ratios = lengths / np.maximum(rest, 1e-30) - 1.0
        edge_rows.append({"frame": fi, "maxExtension": float(np.max(ratios)), "maxCompression": float(np.min(ratios)), "maxAbsStrain": float(np.max(np.abs(ratios))), "p95AbsStrain": float(np.percentile(np.abs(ratios), 95)), "zeroRestSpringMaxLength": float(np.max(lengths[rest < 1e-12])) if np.any(rest < 1e-12) else 0.0})
        n0 = np.cross(neutral[F[:, 1]] - neutral[F[:, 0]], neutral[F[:, 2]] - neutral[F[:, 0]])
        n1 = np.cross(x[F[:, 1]] - x[F[:, 0]], x[F[:, 2]] - x[F[:, 0]])
        a0 = np.linalg.norm(n0, axis=1)
        a1 = np.linalg.norm(n1, axis=1)
        dot = np.einsum("ij,ij->i", n0, n1)
        valid = a0 > max(eye * eye * 1e-12, 1e-30)
        inversion = valid & (dot <= 0.0)
        collapse = valid & (a1 / np.maximum(a0, 1e-30) < 1e-3)
        tri_rows.append({"frame": fi, "inversions": int(np.sum(inversion)), "collapses": int(np.sum(collapse)), "minAreaRatio": float(np.min(a1[valid] / np.maximum(a0[valid], 1e-30))) if np.any(valid) else None, "normalDotMin": float(np.min(dot[valid] / np.maximum(a0[valid] * a1[valid], 1e-30))) if np.any(valid) else None})
    le = np.asarray(landmark_errors)
    er = {k: np.asarray([row[k] for row in edge_rows]) for k in ["maxExtension", "maxCompression", "maxAbsStrain", "p95AbsStrain"]}
    tr = {k: np.asarray([row[k] for row in tri_rows]) for k in ["inversions", "collapses", "minAreaRatio"]}
    wi = np.unravel_index(int(np.argmax(le)), le.shape)
    # Genuine duplicate displacement disagreement in the retained domain.
    tree = cKDTree(neutral)
    pairs = np.asarray(list(tree.query_pairs(1e-10)), dtype=np.int64)
    seam_max = 0.0
    seam_count = int(len(pairs))
    if seam_count:
        seam_max = float(max(np.max(np.linalg.norm(positions[:, pairs[:, 0]] - positions[:, pairs[:, 1]], axis=2)), 0.0))
    report = {"framesValidated": int(len(positions)), "landmarksPerFrame": int(len(T)), "eyeWidth": eye, "landmarkErrorMax": float(le.max()), "landmarkErrorMaxNormalizedEyeWidth": float(le.max() / eye), "worstLandmarkFrame": {"landmarkId": int(wi[1]), "frame": int(wi[0]), "error": float(le[wi]), "errorNormalizedEyeWidth": float(le[wi] / eye)}, "landmarkErrorMedian": float(np.median(le)), "landmarkErrorP95": float(np.percentile(le, 95)), "hardConstraintsWithin1e-8": int(np.sum(le <= 1e-8)), "hardConstraintCount": int(le.size), "edgeStrainWorst": {"maxExtension": float(np.max(er["maxExtension"])), "maxCompression": float(np.min(er["maxCompression"])), "maxAbsStrain": float(np.max(er["maxAbsStrain"])), "p95AbsStrainWorstFrame": float(np.max(er["p95AbsStrain"])), "frameOfMaxAbsStrain": int(np.argmax(er["maxAbsStrain"]))}, "triangleIntegrity": {"maxInversionsAnyFrame": int(np.max(tr["inversions"])), "totalInvertedFrameCounts": int(np.sum(tr["inversions"])), "maxCollapsesAnyFrame": int(np.max(tr["collapses"])), "totalCollapsedFrameCounts": int(np.sum(tr["collapses"])), "minimumAreaRatioAnyFrame": float(np.min(tr["minAreaRatio"])), "frameOfMaxInversions": int(np.argmax(tr["inversions"]))}, "coincidentPatchVertexPairs": seam_count, "maximumSeamPositionDisagreement": seam_max, "selfIntersectionTest": "NOT COMPUTED: no robust triangle-triangle broadphase library is installed; this must be treated as unverified, not zero", "frameEdgeRows": edge_rows, "frameTriangleRows": tri_rows}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["framesValidated", "landmarkErrorMaxNormalizedEyeWidth", "hardConstraintsWithin1e-8", "hardConstraintCount", "edgeStrainWorst", "triangleIntegrity", "maximumSeamPositionDisagreement", "selfIntersectionTest"]}, indent=2))


if __name__ == "__main__":
    main()
