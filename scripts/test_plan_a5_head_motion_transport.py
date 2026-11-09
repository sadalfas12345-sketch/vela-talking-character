"""Synthetic rigid head-motion transport check for the existing attachments.

The stored expression table is head-stabilized, so rigid head motion is not a
facial target in the A5 trajectory.  This test verifies that both characters'
same barycentric correspondence transports a rigid pose without introducing
expression displacement.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser(); p.add_argument("--graph", type=Path, required=True); p.add_argument("--output", type=Path, required=True); p.add_argument("--angle-deg", type=float, default=5.0); p.add_argument("--translation-ipd", type=float, default=0.03); a = p.parse_args()
    g = np.load(a.graph); V = g["V"].astype(float); F = g["constraintTriangles"].astype(np.int64); B = g["constraintBary"].astype(float); P = g["neutralLandmarks"].astype(float)
    eye = float(np.linalg.norm(P[263] - P[33])); center = P.mean(axis=0); right = (P[263] - P[33]) / eye; up = P[[70,63,105,336,293,334]].mean(axis=0) - P[[152,175,199,396,421,428]].mean(axis=0); up -= right * np.dot(up, right); up /= np.linalg.norm(up); depth = np.cross(right, up); depth /= np.linalg.norm(depth)
    c, s = np.cos(np.deg2rad(a.angle_deg)), np.sin(np.deg2rad(a.angle_deg)); R = np.eye(3) + (c - 1.0) * (np.outer(right, right) + np.outer(up, up)) + s * (np.outer(up, right) - np.outer(right, up)); t = float(a.translation_ipd) * eye * right
    Vt = (V - center) @ R.T + center + t; Pt = (P - center) @ R.T + center + t; actual = np.einsum("ij,ijk->ik", B, Vt[F]); errors = np.linalg.norm(actual - Pt, axis=1)
    out = {"vertices": int(len(V)), "landmarks": int(len(P)), "rotationDegrees": float(a.angle_deg), "translationInterocularWidths": float(a.translation_ipd), "maxBarycentricTransportError": float(errors.max()), "rmsBarycentricTransportError": float(np.sqrt(np.mean(errors**2))), "pass": bool(errors.max() < 1e-12), "source": "head-stabilized expression data; synthetic rigid transport only"}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8"); print(json.dumps(out))


if __name__ == "__main__": main()
