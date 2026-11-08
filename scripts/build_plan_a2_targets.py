"""Freeze Plan A2's per-frame 3D landmark targets from the existing 2D table.

The table contains head-stabilized 2D displacement normalized by donor IPD.
This script transfers its right/up components into each Tripo's own neutral
face frame and explicitly sets the unobserved depth component to zero.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--table", type=Path, required=True)
    p.add_argument("--goal1", type=Path, required=True)
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--neutral-frames", type=int, nargs=2, default=[0, 7])
    a = p.parse_args()
    table = json.loads(a.table.read_text(encoding="utf-8"))
    goal = json.loads(a.goal1.read_text(encoding="utf-8"))
    records = {int(r["index"]): r for r in goal["records"] if r.get("meshXYZ") is not None}
    ids = list(range(478))
    missing = [i for i in ids if i not in records]
    if missing:
        raise RuntimeError(f"Goal1 is missing required IDs: {missing}")
    graph = np.load(a.graph)
    attachment_triangles = graph["constraintTriangles"].astype(np.int64)
    barycentric = graph["constraintBary"].astype(np.float64)
    neutral = np.asarray([(barycentric[i][:, None] * graph["V"][attachment_triangles[i]]).sum(axis=0) for i in ids], dtype=np.float64)
    right_raw = neutral[263] - neutral[33]
    eye = float(np.linalg.norm(right_raw))
    right = right_raw / max(eye, 1e-30)
    eye_mid = (neutral[33] + neutral[263]) * 0.5
    up_raw = eye_mid - neutral[152]
    up = up_raw - right * float(np.dot(up_raw, right))
    up /= max(float(np.linalg.norm(up)), 1e-30)
    depth = np.cross(right, up)
    depth /= max(float(np.linalg.norm(depth)), 1e-30)
    rows = table["rows"]
    lo, hi = a.neutral_frames
    neutral_rows = [r for r in rows if lo <= int(r["frame"]) <= hi]
    if not neutral_rows:
        raise RuntimeError("No neutral rows in requested range")
    baseline = np.mean(np.asarray([r["landmarks"] for r in neutral_rows], dtype=np.float64), axis=0)
    all_targets = []
    frame_records = []
    for row in rows:
        disp = np.asarray(row["landmarks"], dtype=np.float64) - baseline
        # The tracked table is already normalized by donor interocular width.
        # Preserve its right/up motion and add exactly zero to unobserved depth.
        delta = disp[:, 0, None] * eye * right[None, :] - disp[:, 1, None] * eye * up[None, :]
        targets = neutral + delta
        all_targets.append(targets)
        frame_records.append({"frame": int(row["frame"]), "timeSeconds": float(row.get("timeSeconds", 0.0)), "source": "existing_stabilized_2d_expression_table", "depthAssumption": "dz=0 in target-character facial-depth axis"})
    # The first stored row is the actual neutral sample.  The table's neutral
    # interval is averaged to suppress tracking noise, but frame 0 must remain
    # the exact original Tripo geometry for the neutral-identity requirement.
    if all_targets:
        all_targets[0] = neutral.copy()
    out_npz = a.output.with_suffix(".npz")
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_npz, targets=np.asarray(all_targets), neutral=neutral, rightAxis=right, upAxis=up, depthAxis=depth, eyeWidth=np.asarray([eye]))
    report = {
        "sourceTable": str(a.table),
        "sourceGoal1": str(a.goal1),
        "sourceGraph": str(a.graph),
        "frameCount": len(rows),
        "landmarkCount": 478,
        "rawValidatedTrajectoryIds": "0-467",
        "tableDerivedTrajectoryIds": "468-477 and stabilized table values for 0-467",
        "neutralFrames": [int(lo), int(hi)],
        "neutralBaselineMethod": "mean of existing stabilized rows in the requested neutral interval",
        "targetCoordinateFrame": {"right": right.tolist(), "up": up.tolist(), "depth": depth.tolist()},
        "targetEyeWidth": eye,
        "assumedDepthChannels": 478 * len(rows),
        "depthAssumption": "No independently measured donor depth is available; every target keeps its own Tripo neutral 3D depth and adds dz=0 along the target facial-depth axis.",
        "provenance": "2D head-stabilized normalized table; IDs 0-467 trace to raw validated tracking, IDs 468-477 are table-derived and are not relabeled raw validated.",
        "frames": frame_records,
        "outputNPZ": str(out_npz),
    }
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frames": len(rows), "landmarks": 478, "eyeWidth": eye, "output": str(out_npz)}))


if __name__ == "__main__":
    main()
